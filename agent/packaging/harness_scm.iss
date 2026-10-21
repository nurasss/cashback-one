; harness_scm.iss
; Test harness to verify Pascal SCM OpenSCManager call with NULL parameters (read-only query).

[Setup]
AppName=SCMHarness
AppVersion=1.0
DefaultDirName={autopf}\SCMHarness
OutputDir=output
OutputBaseFilename=harness_scm
PrivilegesRequired=lowest

[Code]
const
  SC_MANAGER_CONNECT = $0001;

function OpenSCManager(lpMachineName, lpDatabaseName: LongInt; dwDesiredAccess: DWORD): THandle;
  external 'OpenSCManagerW@advapi32.dll stdcall';

function CloseServiceHandle(hSCObject: THandle): BOOL;
  external 'CloseServiceHandle@advapi32.dll stdcall';

function GetLastError(): DWORD;
  external 'GetLastError@kernel32.dll stdcall';

function InitializeSetup(): Boolean;
var
  hSCM: THandle;
  err: DWORD;
  StatusFile: string;
begin
  Result := False; // Never show installer UI
  StatusFile := ExpandConstant('{param:STATUSFILE|}');

  hSCM := OpenSCManager(0, 0, SC_MANAGER_CONNECT);
  if hSCM <> 0 then
  begin
    if StatusFile <> '' then
      SaveStringToFile(StatusFile, 'SUCCESS: Handle=' + IntToStr(hSCM) + #13#10, False);
    CloseServiceHandle(hSCM);
  end
  else
  begin
    err := GetLastError();
    if StatusFile <> '' then
      SaveStringToFile(StatusFile, 'ERROR: WinError=' + IntToStr(err) + #13#10, False);
  end;
end;
