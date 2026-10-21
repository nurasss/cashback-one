// acl_hardening.iss
// Direct Win32 API implementation of exact protected DACL hardening for POSCENTER Loyalty Agent.
// Replaces multi-step icacls commands with an atomic SetNamedSecurityInfoW call,
// eliminating any window of vulnerability for existing sensitive files.
// Shared between installer.iss and harness_acl.iss.

const
  SDDL_REVISION_1 = 1;
  SE_FILE_OBJECT = 1;
  // DACL_SECURITY_INFORMATION ($00000004) or PROTECTED_DACL_SECURITY_INFORMATION ($80000000)
  PROTECTED_DACL_SECURITY_INFORMATION = $80000004;

function ConvertStringSecurityDescriptorToSecurityDescriptorW(
  StringSecurityDescriptor: string;
  StringSDRevision: DWORD;
  var SecurityDescriptor: LongInt;
  var SecurityDescriptorSize: DWORD
): BOOL;
external 'ConvertStringSecurityDescriptorToSecurityDescriptorW@advapi32.dll stdcall';

function GetSecurityDescriptorDacl(
  pSecurityDescriptor: LongInt;
  var lpbDaclPresent: BOOL;
  var pDacl: LongInt;
  var lpbDaclDefaulted: BOOL
): BOOL;
external 'GetSecurityDescriptorDacl@advapi32.dll stdcall';

function SetNamedSecurityInfoW(
  pObjectName: string;
  ObjectType: DWORD;
  SecurityInfo: DWORD;
  psidOwner: LongInt;
  psidGroup: LongInt;
  pDacl: LongInt;
  pSacl: LongInt
): DWORD;
external 'SetNamedSecurityInfoW@advapi32.dll stdcall';

function LocalFree(hMem: LongInt): LongInt;
external 'LocalFree@kernel32.dll stdcall';

function SetExactProtectedDacl(const Path: string; IsDir: Boolean): Boolean;
var
  Sddl: string;
  pSD: LongInt;
  sdSize: DWORD;
  pDacl: LongInt;
  bDaclPresent, bDaclDefaulted: BOOL;
  dwRet: DWORD;
begin
  Result := False;
  pSD := 0;
  pDacl := 0;
  sdSize := 0;

  // D:P = DACL with SE_DACL_PROTECTED (blocks inheritance from parent)
  // SY = NT AUTHORITY\SYSTEM (*S-1-5-18), FA = FILE_ALL_ACCESS
  // BA = BUILTIN\Administrators (*S-1-5-32-544), FA = FILE_ALL_ACCESS
  // OICI = Container & Object inherit (for directory children)
  if IsDir then
    Sddl := 'D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)'
  else
    Sddl := 'D:P(A;;FA;;;SY)(A;;FA;;;BA)';

  if not ConvertStringSecurityDescriptorToSecurityDescriptorW(
    Sddl, SDDL_REVISION_1, pSD, sdSize) then
    Exit;

  try
    if not GetSecurityDescriptorDacl(pSD, bDaclPresent, pDacl, bDaclDefaulted) then
      Exit;

    if not bDaclPresent then
      Exit;

    if pDacl = 0 then
      Exit;

    // Atomically replaces DACL and marks it SE_DACL_PROTECTED in a single kernel call
    dwRet := SetNamedSecurityInfoW(
      Path,
      SE_FILE_OBJECT,
      PROTECTED_DACL_SECURITY_INFORMATION,
      0, 0,
      pDacl,
      0
    );

    Result := (dwRet = 0);
  finally
    if pSD <> 0 then
      LocalFree(pSD);
  end;
end;

function SecureDirectoryAcl(const DirPath: string): Boolean;
begin
  Result := SetExactProtectedDacl(DirPath, True);
end;

function SecureFileAcl(const FilePath: string): Boolean;
begin
  Result := SetExactProtectedDacl(FilePath, False);
end;
