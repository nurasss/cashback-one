// harness_serializer.iss
// Test harness to execute actual Pascal configuration serialization and validation routines.

[Setup]
AppName=ConfigSerializerHarness
AppVersion=1.0
DefaultDirName={autopf}\ConfigSerializerHarness
OutputDir=output
OutputBaseFilename=harness_serializer
PrivilegesRequired=lowest

[Code]
#include "config_serializer.iss"

function GetParamValue(const Lines: TArrayOfString; const Key: string): string;
var
  I: Integer;
  Line, Prefix: string;
begin
  Result := '';
  Prefix := Key + '=';
  for I := 0 to GetArrayLength(Lines) - 1 do
  begin
    Line := Lines[I];
    if Pos(Prefix, Line) = 1 then
    begin
      Result := Copy(Line, Length(Prefix) + 1, Length(Line) - Length(Prefix));
      Exit;
    end;
  end;
end;

function InitializeSetup(): Boolean;
var
  ParamFile: string;
  Lines: TArrayOfString;
  Mode, OutFile, StatusFile: string;
  CloudUrl, ApiKey, OnePath, OneUser, OnePass: string;
  CheckField, CheckVal, ErrMsg: string;
begin
  Result := False; // Never show installer UI

  ParamFile := ExpandConstant('{param:INIFILE|}');
  if ParamFile = '' then
    ParamFile := ExpandConstant('{param:PARAMFILE|}');

  if (ParamFile <> '') and FileExists(ParamFile) then
  begin
    if LoadStringsFromFile(ParamFile, Lines) then
    begin
      Mode := GetParamValue(Lines, 'Mode');
      OutFile := GetParamValue(Lines, 'OutFile');
      StatusFile := GetParamValue(Lines, 'StatusFile');
      CheckField := GetParamValue(Lines, 'CheckField');
      CheckVal := GetParamValue(Lines, 'CheckVal');
      CloudUrl := GetParamValue(Lines, 'CloudUrl');
      ApiKey := GetParamValue(Lines, 'ApiKey');
      OnePath := GetParamValue(Lines, 'OnePath');
      OneUser := GetParamValue(Lines, 'OneUser');
      OnePass := GetParamValue(Lines, 'OnePass');
    end;
  end;

  if Mode = '' then
    Mode := 'serialize';

  if Mode = 'validate' then
  begin
    // Support testing newlines by unescaping literal \r and \n in test value
    StringChangeEx(CheckVal, '\r', #13, True);
    StringChangeEx(CheckVal, '\n', #10, True);

    if CheckDisallowedInputMsg(CheckField, CheckVal, ErrMsg) then
    begin
      if StatusFile <> '' then
        SaveStringToFile(StatusFile, UTF8Encode('VALID' + #13#10), False);
    end
    else
    begin
      if StatusFile <> '' then
        SaveStringToFile(StatusFile, UTF8Encode('INVALID: ' + ErrMsg + #13#10), False);
    end;
    Exit;
  end;

  // Mode = 'serialize'
  if not CheckDisallowedInputMsg('Cloud URL', CloudUrl, ErrMsg) then
  begin
    if StatusFile <> '' then
      SaveStringToFile(StatusFile, UTF8Encode('ERROR: ' + ErrMsg + #13#10), False);
    Exit;
  end;
  if not CheckDisallowedInputMsg('API Key', ApiKey, ErrMsg) then
  begin
    if StatusFile <> '' then
      SaveStringToFile(StatusFile, UTF8Encode('ERROR: ' + ErrMsg + #13#10), False);
    Exit;
  end;
  if not CheckDisallowedInputMsg('1C Path', OnePath, ErrMsg) then
  begin
    if StatusFile <> '' then
      SaveStringToFile(StatusFile, UTF8Encode('ERROR: ' + ErrMsg + #13#10), False);
    Exit;
  end;
  if not CheckDisallowedInputMsg('1C User', OneUser, ErrMsg) then
  begin
    if StatusFile <> '' then
      SaveStringToFile(StatusFile, UTF8Encode('ERROR: ' + ErrMsg + #13#10), False);
    Exit;
  end;
  if not CheckDisallowedInputMsg('1C Pass', OnePass, ErrMsg) then
  begin
    if StatusFile <> '' then
      SaveStringToFile(StatusFile, UTF8Encode('ERROR: ' + ErrMsg + #13#10), False);
    Exit;
  end;

  if OutFile <> '' then
  begin
    if SerializeConfigToFile(OutFile, CloudUrl, ApiKey, OnePath, OneUser, OnePass) then
    begin
      if StatusFile <> '' then
        SaveStringToFile(StatusFile, UTF8Encode('SUCCESS' + #13#10), False);
    end
    else
    begin
      if StatusFile <> '' then
        SaveStringToFile(StatusFile, UTF8Encode('ERROR: Failed to write file' + #13#10), False);
    end;
  end;
end;
