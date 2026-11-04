// config_serializer.iss
// Common configuration serialization routines for POSCENTER Loyalty Agent
// Shared between production installer (installer.iss) and test harnesses.

const
  CRYPTPROTECT_LOCAL_MACHINE = $00000004;
  CRYPTPROTECT_UI_FORBIDDEN = $00000001;
  CRYPT_STRING_BASE64 = $00000001;
  CRYPT_STRING_NOCRLF = $40000000;
  CP_UTF8 = 65001;
  DPAPI_ENTROPY_STR = 'POSCENTER_LOYALTY_AGENT_DPAPI_SALT_v1';

type
  TDataBlob = record
    cbData: DWORD;
    pbData: LongInt;
  end;

function LocalAlloc(uFlags, uBytes: DWORD): LongInt;
  external 'LocalAlloc@kernel32.dll stdcall';

procedure CopyMemoryFromAnsi(Dest: LongInt; const Source: AnsiString; Length: DWORD);
  external 'RtlMoveMemory@kernel32.dll stdcall';

function MultiByteToWideChar(
  CodePage: UINT;
  dwFlags: DWORD;
  lpMultiByteStr: LongInt;
  cbMultiByte: Integer;
  lpWideCharStr: string;
  cchWideChar: Integer
): Integer;
external 'MultiByteToWideChar@kernel32.dll stdcall';

function CryptProtectData(
  var pDataIn: TDataBlob;
  szDataDescr: LongInt;
  var pOptionalEntropy: TDataBlob;
  pvReserved: LongInt;
  pPromptStruct: LongInt;
  dwFlags: DWORD;
  var pDataOut: TDataBlob
): BOOL;
external 'CryptProtectData@crypt32.dll stdcall';

function CryptUnprotectData(
  var pDataIn: TDataBlob;
  ppszDataDescr: LongInt;
  var pOptionalEntropy: TDataBlob;
  pvReserved: LongInt;
  pPromptStruct: LongInt;
  dwFlags: DWORD;
  var pDataOut: TDataBlob
): BOOL;
external 'CryptUnprotectData@crypt32.dll stdcall';

function CryptBinaryToStringW(
  pbBinary: LongInt;
  cbBinary: DWORD;
  dwFlags: DWORD;
  pszString: string;
  var pcchString: DWORD
): BOOL;
external 'CryptBinaryToStringW@crypt32.dll stdcall';

function CryptStringToBinaryW(
  pszString: string;
  cchString: DWORD;
  dwFlags: DWORD;
  pbBinary: LongInt;
  var pcbBinary: DWORD;
  pdwSkip: LongInt;
  pdwFlags: LongInt
): BOOL;
external 'CryptStringToBinaryW@crypt32.dll stdcall';

function Escape1CParam(const S: string): string;
var
  Esc: string;
begin
  Esc := S;
  StringChangeEx(Esc, '"', '""', True);
  Result := Esc;
end;

function FormatDotEnvValue(const S: string): string;
var
  Escaped: string;
begin
  // In python-dotenv, single-quoted values parse \\ as \.
  // To preserve literal backslashes (including UNC paths \\server\share and passwords),
  // every single backslash must be doubled before wrapping in single quotes.
  Escaped := S;
  StringChangeEx(Escaped, '\', '\\', True);
  Result := '''' + Escaped + '''';
end;

function UnquoteDotEnvValue(const S: string): string;
var
  Val: string;
begin
  Val := Trim(S);
  if (Length(Val) >= 2) and (Val[1] = '''') and (Val[Length(Val)] = '''') then
  begin
    Val := Copy(Val, 2, Length(Val) - 2);
    StringChangeEx(Val, '\\', '\', True);
  end
  else if (Length(Val) >= 2) and (Val[1] = '"') and (Val[Length(Val)] = '"') then
  begin
    Val := Copy(Val, 2, Length(Val) - 2);
    StringChangeEx(Val, '\\', '\', True);
  end;
  Result := Val;
end;

function CheckDisallowedInputMsg(const FieldName, S: string; var OutErrMsg: string): Boolean;
begin
  Result := True;
  OutErrMsg := '';
  if Pos('${', S) > 0 then
  begin
    OutErrMsg := FieldName + ': значение содержит недопустимую последовательность "${". Символы "${" зарезервированы для подстановки переменных окружения.';
    Result := False;
    Exit;
  end;
  if Pos('''', S) > 0 then
  begin
    OutErrMsg := FieldName + ': символ одинарной кавычки ('') не поддерживается в строках подключения.';
    Result := False;
    Exit;
  end;
  if (Pos(#13, S) > 0) or (Pos(#10, S) > 0) then
  begin
    OutErrMsg := FieldName + ': переносы строк недопустимы.';
    Result := False;
    Exit;
  end;
end;

function CheckDisallowedInput(const FieldName, S: string): Boolean;
var
  ErrMsg: string;
begin
  Result := CheckDisallowedInputMsg(FieldName, S, ErrMsg);
  if not Result then
  begin
    MsgBox(ErrMsg, mbError, MB_OK);
  end;
end;

function ProtectSecretDPAPI(const PlainText: string; var OutBase64: string): Boolean;
var
  DataIn, DataEntropy, DataOut: TDataBlob;
  PlainAnsi, EntropyAnsi: AnsiString;
  PlainLen, EntropyLen: DWORD;
  pIn, pEntropy: LongInt;
  cchOut: DWORD;
  Base64Buf: string;
begin
  Result := False;
  OutBase64 := '';
  if PlainText = '' then
  begin
    Result := True;
    Exit;
  end;

  PlainAnsi := UTF8Encode(PlainText);
  PlainLen := Length(PlainAnsi);
  EntropyAnsi := AnsiString(DPAPI_ENTROPY_STR);
  EntropyLen := Length(EntropyAnsi);

  pIn := LocalAlloc(0, PlainLen);
  pEntropy := LocalAlloc(0, EntropyLen);
  if (pIn = 0) or (pEntropy = 0) then
  begin
    if pIn <> 0 then LocalFree(pIn);
    if pEntropy <> 0 then LocalFree(pEntropy);
    Exit;
  end;

  try
    CopyMemoryFromAnsi(pIn, PlainAnsi, PlainLen);
    CopyMemoryFromAnsi(pEntropy, EntropyAnsi, EntropyLen);

    DataIn.cbData := PlainLen;
    DataIn.pbData := pIn;
    DataEntropy.cbData := EntropyLen;
    DataEntropy.pbData := pEntropy;
    DataOut.cbData := 0;
    DataOut.pbData := 0;

    if not CryptProtectData(
      DataIn,
      0,
      DataEntropy,
      0,
      0,
      CRYPTPROTECT_LOCAL_MACHINE or CRYPTPROTECT_UI_FORBIDDEN,
      DataOut
    ) then
      Exit;

    try
      cchOut := 0;
      if not CryptBinaryToStringW(
        DataOut.pbData,
        DataOut.cbData,
        CRYPT_STRING_BASE64 or CRYPT_STRING_NOCRLF,
        '',
        cchOut
      ) then
        Exit;

      SetLength(Base64Buf, cchOut);
      if not CryptBinaryToStringW(
        DataOut.pbData,
        DataOut.cbData,
        CRYPT_STRING_BASE64 or CRYPT_STRING_NOCRLF,
        Base64Buf,
        cchOut
      ) then
        Exit;

      while (Length(Base64Buf) > 0) and (
        (Base64Buf[Length(Base64Buf)] = #0) or
        (Base64Buf[Length(Base64Buf)] = #13) or
        (Base64Buf[Length(Base64Buf)] = #10) or
        (Base64Buf[Length(Base64Buf)] = ' ')
      ) do
        SetLength(Base64Buf, Length(Base64Buf) - 1);

      OutBase64 := Base64Buf;
      Result := True;
    finally
      if DataOut.pbData <> 0 then
        LocalFree(DataOut.pbData);
    end;
  finally
    if pIn <> 0 then LocalFree(pIn);
    if pEntropy <> 0 then LocalFree(pEntropy);
  end;
end;

function UnprotectSecretDPAPI(const InBase64: string; var OutPlainText: string): Boolean;
var
  DataIn, DataEntropy, DataOut: TDataBlob;
  EntropyAnsi: AnsiString;
  EntropyLen, cbBinary: DWORD;
  pIn, pEntropy: LongInt;
  CleanB64: string;
  cchWide: Integer;
  WideBuf: string;
begin
  Result := False;
  OutPlainText := '';
  CleanB64 := Trim(InBase64);
  if CleanB64 = '' then
  begin
    Result := True;
    Exit;
  end;

  cbBinary := 0;
  if not CryptStringToBinaryW(CleanB64, Length(CleanB64), CRYPT_STRING_BASE64, 0, cbBinary, 0, 0) then
    Exit;

  pIn := LocalAlloc(0, cbBinary);
  EntropyAnsi := AnsiString(DPAPI_ENTROPY_STR);
  EntropyLen := Length(EntropyAnsi);
  pEntropy := LocalAlloc(0, EntropyLen);

  if (pIn = 0) or (pEntropy = 0) then
  begin
    if pIn <> 0 then LocalFree(pIn);
    if pEntropy <> 0 then LocalFree(pEntropy);
    Exit;
  end;

  try
    if not CryptStringToBinaryW(CleanB64, Length(CleanB64), CRYPT_STRING_BASE64, pIn, cbBinary, 0, 0) then
      Exit;

    CopyMemoryFromAnsi(pEntropy, EntropyAnsi, EntropyLen);

    DataIn.cbData := cbBinary;
    DataIn.pbData := pIn;
    DataEntropy.cbData := EntropyLen;
    DataEntropy.pbData := pEntropy;
    DataOut.cbData := 0;
    DataOut.pbData := 0;

    if not CryptUnprotectData(
      DataIn,
      0,
      DataEntropy,
      0,
      0,
      CRYPTPROTECT_UI_FORBIDDEN,
      DataOut
    ) then
      Exit;

    try
      cchWide := MultiByteToWideChar(CP_UTF8, 0, DataOut.pbData, DataOut.cbData, '', 0);
      if cchWide <= 0 then
      begin
        OutPlainText := '';
        Result := True;
        Exit;
      end;

      SetLength(WideBuf, cchWide);
      MultiByteToWideChar(CP_UTF8, 0, DataOut.pbData, DataOut.cbData, WideBuf, cchWide);
      OutPlainText := WideBuf;
      Result := True;
    finally
      if DataOut.pbData <> 0 then
        LocalFree(DataOut.pbData);
    end;
  finally
    if pIn <> 0 then LocalFree(pIn);
    if pEntropy <> 0 then LocalFree(pEntropy);
  end;
end;

function Extract1CParam(const ConnStr, ParamName: string): string;
var
  Idx, StartIdx, I: Integer;
  Prefix, Res: string;
  InQuote: Boolean;
begin
  Result := '';
  Prefix := ParamName + '="';
  Idx := Pos(Lowercase(Prefix), Lowercase(ConnStr));
  if Idx > 0 then
  begin
    StartIdx := Idx + Length(Prefix);
    Res := '';
    I := StartIdx;
    while I <= Length(ConnStr) do
    begin
      if ConnStr[I] = '"' then
      begin
        if (I < Length(ConnStr)) and (ConnStr[I + 1] = '"') then
        begin
          Res := Res + '"';
          I := I + 2;
          Continue;
        end
        else
        begin
          Break;
        end;
      end
      else
      begin
        Res := Res + ConnStr[I];
        I := I + 1;
      end;
    end;
    Result := Res;
    Exit;
  end;

  Prefix := ParamName + '=';
  Idx := Pos(Lowercase(Prefix), Lowercase(ConnStr));
  if Idx > 0 then
  begin
    StartIdx := Idx + Length(Prefix);
    Res := '';
    for I := StartIdx to Length(ConnStr) do
    begin
      if ConnStr[I] = ';' then
        Break;
      Res := Res + ConnStr[I];
    end;
    Result := Trim(Res);
  end;
end;

function Strip1CPwdParam(const ConnStr: string): string;
var
  Idx, I, EndIdx: Integer;
  Prefix: string;
  Res: string;
begin
  Result := ConnStr;
  Prefix := 'pwd="';
  Idx := Pos(Lowercase(Prefix), Lowercase(ConnStr));
  if Idx > 0 then
  begin
    I := Idx + Length(Prefix);
    while I <= Length(ConnStr) do
    begin
      if ConnStr[I] = '"' then
      begin
        if (I < Length(ConnStr)) and (ConnStr[I + 1] = '"') then
        begin
          I := I + 2;
          Continue;
        end
        else
        begin
          EndIdx := I;
          if (EndIdx < Length(ConnStr)) and (ConnStr[EndIdx + 1] = ';') then
            EndIdx := EndIdx + 1;
          Res := Copy(ConnStr, 1, Idx - 1) + Copy(ConnStr, EndIdx + 1, Length(ConnStr) - EndIdx);
          Result := Res;
          Exit;
        end;
      end;
      I := I + 1;
    end;
  end;

  Prefix := 'pwd=';
  Idx := Pos(Lowercase(Prefix), Lowercase(ConnStr));
  if Idx > 0 then
  begin
    EndIdx := Length(ConnStr);
    for I := Idx + Length(Prefix) to Length(ConnStr) do
    begin
      if ConnStr[I] = ';' then
      begin
        EndIdx := I;
        Break;
      end;
    end;
    Result := Copy(ConnStr, 1, Idx - 1) + Copy(ConnStr, EndIdx + 1, Length(ConnStr) - EndIdx);
  end;
end;

function BuildDotEnvContent(const CloudUrl, ApiKeyDpapi, ConnString, PassDpapi: string): string;
begin
  Result := 'AGENT_ENV=''production''' + #13#10 +
    'AGENT_CLOUD_BASE_URL=' + FormatDotEnvValue(CloudUrl) + #13#10 +
    'AGENT_API_KEY_DPAPI=' + FormatDotEnvValue(ApiKeyDpapi) + #13#10 +
    'ONE_ADAPTER_MODE=''com''' + #13#10 +
    'ONE_CONNECTION_STRING=' + FormatDotEnvValue(ConnString) + #13#10 +
    'ONE_PASSWORD_DPAPI=' + FormatDotEnvValue(PassDpapi) + #13#10 +
    'AGENT_POLL_INTERVAL_SECONDS=''300''' + #13#10 +
    'AGENT_CLAMP_NEGATIVE_BALANCE=''false''' + #13#10;
end;

function SerializeConfigToFile(const FilePath, CloudUrl, ApiKey, DbPath, User, Pass: string): Boolean;
var
  ApiKeyDpapi, PassDpapi, ConnString, EnvContent: string;
begin
  Result := False;
  if not ProtectSecretDPAPI(ApiKey, ApiKeyDpapi) then
    Exit;
  if not ProtectSecretDPAPI(Pass, PassDpapi) then
    Exit;
  ConnString := 'File="' + Escape1CParam(DbPath) + '";Usr="' + Escape1CParam(User) + '";';
  EnvContent := BuildDotEnvContent(CloudUrl, ApiKeyDpapi, ConnString, PassDpapi);
  Result := SaveStringToFile(FilePath, UTF8Encode(EnvContent), False);
end;

function UpdateExistingConfigFile(const FilePath, NewApiKey, NewPass: string): Boolean;
var
  OldLines: TArrayOfString;
  NewContent: string;
  I: Integer;
  Line, LineTrim: string;
  RawVal, EncVal: string;
  PassToEncrypt, ExtractedPwd: string;
  OnePassDpapiInserted: Boolean;
  TmpFile: string;
begin
  Result := False;
  if not FileExists(FilePath) then
    Exit;

  if not LoadStringsFromFile(FilePath, OldLines) then
    Exit;

  NewContent := '';
  PassToEncrypt := NewPass;
  OnePassDpapiInserted := False;

  for I := 0 to GetArrayLength(OldLines) - 1 do
  begin
    Line := OldLines[I];
    LineTrim := Trim(Line);

    if Pos('AGENT_API_KEY=', LineTrim) = 1 then
    begin
      // Plaintext legacy key: upgrade to AGENT_API_KEY_DPAPI
      if NewApiKey <> '' then
        RawVal := NewApiKey
      else
        RawVal := UnquoteDotEnvValue(Copy(LineTrim, Length('AGENT_API_KEY=') + 1, Length(LineTrim)));
      if not ProtectSecretDPAPI(RawVal, EncVal) then
        Exit;
      NewContent := NewContent + 'AGENT_API_KEY_DPAPI=' + FormatDotEnvValue(EncVal) + #13#10;
    end
    else if Pos('AGENT_API_KEY_DPAPI=', LineTrim) = 1 then
    begin
      if NewApiKey <> '' then
      begin
        if not ProtectSecretDPAPI(NewApiKey, EncVal) then
          Exit;
        NewContent := NewContent + 'AGENT_API_KEY_DPAPI=' + FormatDotEnvValue(EncVal) + #13#10;
      end
      else
      begin
        NewContent := NewContent + Line + #13#10;
      end;
    end
    else if Pos('ONE_CONNECTION_STRING=', LineTrim) = 1 then
    begin
      RawVal := UnquoteDotEnvValue(Copy(LineTrim, Length('ONE_CONNECTION_STRING=') + 1, Length(LineTrim)));
      ExtractedPwd := Extract1CParam(RawVal, 'Pwd');
      if (PassToEncrypt = '') and (ExtractedPwd <> '') then
        PassToEncrypt := ExtractedPwd;

      // Strip Pwd from connection string
      RawVal := Strip1CPwdParam(RawVal);
      NewContent := NewContent + 'ONE_CONNECTION_STRING=' + FormatDotEnvValue(RawVal) + #13#10;

      // If we have a password to encrypt and haven't encountered ONE_PASSWORD_DPAPI yet
      if PassToEncrypt <> '' then
      begin
        if not ProtectSecretDPAPI(PassToEncrypt, EncVal) then
          Exit;
        NewContent := NewContent + 'ONE_PASSWORD_DPAPI=' + FormatDotEnvValue(EncVal) + #13#10;
        OnePassDpapiInserted := True;
      end;
    end
    else if Pos('ONE_PASSWORD_DPAPI=', LineTrim) = 1 then
    begin
      if OnePassDpapiInserted then
      begin
        // Already inserted right after ONE_CONNECTION_STRING, skip duplicate line
      end
      else if NewPass <> '' then
      begin
        if not ProtectSecretDPAPI(NewPass, EncVal) then
          Exit;
        NewContent := NewContent + 'ONE_PASSWORD_DPAPI=' + FormatDotEnvValue(EncVal) + #13#10;
        OnePassDpapiInserted := True;
      end
      else
      begin
        NewContent := NewContent + Line + #13#10;
        OnePassDpapiInserted := True;
      end;
    end
    else
    begin
      // Keep line byte-for-byte intact
      NewContent := NewContent + Line + #13#10;
    end;
  end;

  TmpFile := FilePath + '.tmp';
  if not SaveStringToFile(TmpFile, UTF8Encode(NewContent), False) then
    Exit;

  // Protect temp file with exact DACL before moving
  if not SecureFileAcl(TmpFile) then
  begin
    DeleteFile(TmpFile);
    Exit;
  end;

  if FileExists(FilePath) then
    DeleteFile(FilePath);

  if not RenameFile(TmpFile, FilePath) then
    Exit;

  Result := SecureFileAcl(FilePath);
end;
