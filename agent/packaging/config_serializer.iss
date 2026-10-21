// config_serializer.iss
// Common configuration serialization routines for POSCENTER Loyalty Agent
// Shared between production installer (installer.iss) and test harness.

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

function Build1CConnectionString(const DbPath, User, Pass: string): string;
begin
  Result := 'File="' + Escape1CParam(DbPath) + '";Usr="' + Escape1CParam(User) + '";Pwd="' + Escape1CParam(Pass) + '";';
end;

function BuildDotEnvContent(const CloudUrl, ApiKey, ConnString: string): string;
begin
  Result := 'AGENT_ENV=''production''' + #13#10 +
    'AGENT_CLOUD_BASE_URL=' + FormatDotEnvValue(CloudUrl) + #13#10 +
    'AGENT_API_KEY=' + FormatDotEnvValue(ApiKey) + #13#10 +
    'ONE_ADAPTER_MODE=''com''' + #13#10 +
    'ONE_CONNECTION_STRING=' + FormatDotEnvValue(ConnString) + #13#10 +
    'AGENT_POLL_INTERVAL_SECONDS=''300''' + #13#10 +
    'AGENT_CLAMP_NEGATIVE_BALANCE=''false''' + #13#10;
end;

function SerializeConfigToFile(const FilePath, CloudUrl, ApiKey, DbPath, User, Pass: string): Boolean;
var
  ConnString, EnvContent: string;
begin
  ConnString := Build1CConnectionString(DbPath, User, Pass);
  EnvContent := BuildDotEnvContent(CloudUrl, ApiKey, ConnString);
  // Write strictly in UTF-8
  Result := SaveStringToFile(FilePath, UTF8Encode(EnvContent), False);
end;
