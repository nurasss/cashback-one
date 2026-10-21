; harness_acl.iss
; Test harness to verify Pascal Win32 API ACL hardening on directories and files.
; Shared include: acl_hardening.iss

[Setup]
AppName=AclHarness
AppVersion=1.0
DefaultDirName={autopf}\AclHarness
OutputDir=output
OutputBaseFilename=harness_acl
PrivilegesRequired=lowest

[Code]
#include "acl_hardening.iss"

function InitializeSetup(): Boolean;
var
  TargetPath: string;
  IsDirParam: string;
  StatusFile: string;
  Ok: Boolean;
begin
  Result := False; // Never show installer UI
  TargetPath := ExpandConstant('{param:TARGET|}');
  IsDirParam := ExpandConstant('{param:ISDIR|0}');
  StatusFile := ExpandConstant('{param:STATUSFILE|}');

  if TargetPath <> '' then
  begin
    if IsDirParam = '1' then
      Ok := SecureDirectoryAcl(TargetPath)
    else
      Ok := SecureFileAcl(TargetPath);

    if StatusFile <> '' then
    begin
      if Ok then
        SaveStringToFile(StatusFile, 'SUCCESS' + #13#10, False)
      else
        SaveStringToFile(StatusFile, 'FAILED' + #13#10, False);
    end;
  end;
end;
