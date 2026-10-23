; Inno Setup 6 Script for POSCENTER Loyalty Agent
; Builds single CashbackOneAgent-Setup.exe installer

#define MyAppName "POSCENTER Loyalty Agent"
#define MyAppVersion "0.2.2"
#define MyAppPublisher "POSCENTER"
#define MyAppURL "https://cashback-qr.poscenter.kz"
#define MyAppExeName "CashbackOneAgent.exe"
#define MyServiceName "POSCENTERLoyaltyAgent"

[Setup]
AppId={{C1A588A6-9E45-4DC3-8108-72787889A190}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf32}\POSCENTER\LoyaltyAgent
DefaultGroupName=POSCENTER Loyalty
DisableProgramGroupPage=yes
PrivilegesRequired=admin
OutputDir=output
OutputBaseFilename=CashbackOneAgent-Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x86 x64compatible arm64
ArchitecturesInstallIn64BitMode=
UninstallDisplayIcon={app}\{#MyAppExeName}
CloseApplications=yes
CloseApplicationsFilter=*.exe
RestartApplications=no

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[CustomMessages]
russian.ComConnectorWarning=Внимание: В системе не обнаружен зарегистрированный 32-битный COM-соединитель 1С:Предприятия (V83.COMConnector).%n%nДля синхронизации с базой POSCENTER ONE требуется установленная 32-битная платформа 1С:Предприятие 8.3 с зарегистрированной библиотекой comcntr.dll (regsvr32).%n%nУстановка агента будет продолжена, но для работы синхронизации администратору потребуется зарегистрировать comcntr.dll.
russian.UpgradePageTitle=Обновление POSCENTER Loyalty Agent
russian.UpgradePageDesc=Обнаружена существующая установка и конфигурация агента.
russian.UpgradeKeepConfig=Сохранить существующие настройки подключения и синхронизации (Рекомендуется)
russian.UpgradeReconfigure=Изменить настройки подключения (облако, 1С, маппинг)
russian.ReconfigureBlockedDueToState=Внимание: обнаружена существующая база состояния синхронизации (agent_state.db).%n%nИзменение параметров подключения к 1С или облаку заблокировано во избежание смешивания курсоров и состояния разных баз или клиентов.%n%nДля смены базы или клиента требуется отдельная процедура миграции.%n%nОбновление возможно только с сохранением текущих настроек.
russian.CloudPageTitle=Настройка подключения к облаку
russian.CloudPageDesc=Укажите параметры подключения агента к облаку Cashback One.
russian.CloudUrlLabel=Адрес облачного сервера (HTTPS):
russian.ApiKeyLabel=Секретный ключ агента (Agent API Key):
russian.OnePageTitle=Подключение к базе POSCENTER ONE
russian.OnePageDesc=Укажите путь к файловой базе данных 1С и пользователя с правами только для чтения.
russian.OneDbPathLabel=Каталог файловой базы 1С (содержит 1Cv8.1CD):
russian.OneUserLabel=Пользователь 1С (только чтение):
russian.OnePassLabel=Пароль пользователя 1С:
russian.MappingPageTitle=Маппинг метаданных POSCENTER ONE
russian.MappingPageDesc=Укажите подтверждённый файл маппинга stage0_mapping.json.
russian.MappingFileLabel=Файл маппинга (stage0_mapping.json):
russian.MappingInfo=Агент обращается к 1С строго по подтверждённому маппингу метаданных и не угадывает имена объектов базы данных.
russian.StopServiceTimeout=Не удалось остановить службу POSCENTERLoyaltyAgent перед установкой (превышено время ожидания 30 сек). Пожалуйста, остановите службу вручную перед продолжением.
russian.AclFailed=Ошибка применения прав безопасности (ACL). Запись секретов отменена в целях безопасности.
russian.MappingValidationFailed=Файл маппинга не прошёл проверку валидатором stage0 validate-mapping (--require-verified). Убедитесь, что все ключевые метаданные (карты, операции, остатки) подтверждены.
russian.ServiceInstallFailed=Ошибка регистрации службы Windows POSCENTERLoyaltyAgent через исполняемый файл агента.
russian.ServiceRunningNotice=Служба POSCENTERLoyaltyAgent успешно запущена в фоновом режиме.%n%nВнимание: статус службы 'Работает' подтверждает запуск процесса агента, но не гарантирует успешную синхронизацию с 1С и облаком. Проверьте журнал C:\ProgramData\POSCENTER\LoyaltyAgent\logs\agent.log или состояние через команду CashbackOneAgent.exe status.
russian.ServiceStartTimeout=Службе POSCENTERLoyaltyAgent не удалось перейти в состояние 'Работает' за отведённое время. Проверьте журнал C:\ProgramData\POSCENTER\LoyaltyAgent\logs\agent.log.
russian.PurgeSecretsPrompt=Удалить файл конфигурации (.env.service) с секретными ключами?%n%n(База контрольных точек синхронизации и HMAC-ключ останутся сохранены).

[Files]
Source: "dist\CashbackOneAgent\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Code]
#include "config_serializer.iss"
#include "acl_hardening.iss"

const
  SC_MANAGER_CONNECT = $0001;
  SERVICE_QUERY_STATUS = $0004;
  SERVICE_STOPPED = $00000001;
  SERVICE_START_PENDING = $00000002;
  SERVICE_STOP_PENDING = $00000003;
  SERVICE_RUNNING = $00000004;
  ERROR_SUCCESS = 0;
  ERROR_SERVICE_DOES_NOT_EXIST = 1060;

type
  TServiceStatus = record
    dwServiceType: DWORD;
    dwCurrentState: DWORD;
    dwControlsAccepted: DWORD;
    dwWin32ExitCode: DWORD;
    dwServiceSpecificExitCode: DWORD;
    dwCheckPoint: DWORD;
    dwWaitHint: DWORD;
  end;

function OpenSCManager(lpMachineName, lpDatabaseName: LongInt; dwDesiredAccess: DWORD): THandle;
  external 'OpenSCManagerW@advapi32.dll stdcall';

function OpenService(hSCManager: THandle; lpServiceName: string; dwDesiredAccess: DWORD): THandle;
  external 'OpenServiceW@advapi32.dll stdcall';

function QueryServiceStatus(hService: THandle; var lpServiceStatus: TServiceStatus): BOOL;
  external 'QueryServiceStatus@advapi32.dll stdcall';

function CloseServiceHandle(hSCObject: THandle): BOOL;
  external 'CloseServiceHandle@advapi32.dll stdcall';

function GetLastError(): DWORD;
  external 'GetLastError@kernel32.dll stdcall';

var
  IsUpgradeMode: Boolean;
  HasExistingStateDb: Boolean;
  PageUpgrade: TWizardPage;
  RadioKeepConfig: TRadioButton;
  RadioReconfigure: TRadioButton;

  PageCloud: TWizardPage;
  EditCloudUrl: TNewEdit;
  EditApiKey: TNewEdit;

  PageOne: TWizardPage;
  EditOneDbPath: TNewEdit;
  BtnBrowseDb: TNewButton;
  EditOneUser: TNewEdit;
  EditOnePass: TNewEdit;

  PageMapping: TWizardPage;
  EditMappingPath: TNewEdit;
  BtnBrowseMapping: TNewButton;

function QueryServiceStateEx(const ServiceName: string; var SvcState: DWORD; var LastErr: DWORD): Boolean;
var
  hSCM, hSvc: THandle;
  Status: TServiceStatus;
begin
  Result := False;
  SvcState := 0;
  LastErr := ERROR_SUCCESS;

  // Pass 0 (NULL) for machine and database to use default local active SCM database without error 123
  hSCM := OpenSCManager(0, 0, SC_MANAGER_CONNECT);
  if hSCM = 0 then
  begin
    LastErr := GetLastError();
    Exit;
  end;

  try
    hSvc := OpenService(hSCM, ServiceName, SERVICE_QUERY_STATUS);
    if hSvc = 0 then
    begin
      LastErr := GetLastError();
      Exit;
    end;

    try
      if QueryServiceStatus(hSvc, Status) then
      begin
        SvcState := Status.dwCurrentState;
        Result := True;
      end
      else
      begin
        LastErr := GetLastError();
      end;
    finally
      CloseServiceHandle(hSvc);
    end;
  finally
    CloseServiceHandle(hSCM);
  end;
end;

function Check1CComConnector(): Boolean;
var
  ComObj: Variant;
begin
  Result := False;
  try
    ComObj := CreateOleObject('V83.COMConnector');
    Result := True;
  except
    Result := False;
  end;
end;

function InitializeSetup(): Boolean;
var
  EnvFilePath, StateDbPath: string;
begin
  Result := True;
  EnvFilePath := ExpandConstant('{commonappdata}\POSCENTER\LoyaltyAgent\config\.env.service');
  StateDbPath := ExpandConstant('{commonappdata}\POSCENTER\LoyaltyAgent\state\agent_state.db');
  IsUpgradeMode := FileExists(EnvFilePath);
  HasExistingStateDb := FileExists(StateDbPath);

  if not Check1CComConnector() then
  begin
    MsgBox(CustomMessage('ComConnectorWarning'), mbInformation, MB_OK);
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  SvcState, LastErr: DWORD;
  I, ResultCode: Integer;
begin
  Result := '';
  if QueryServiceStateEx('{#MyServiceName}', SvcState, LastErr) then
  begin
    if (SvcState <> 0) and (SvcState <> SERVICE_STOPPED) then
    begin
      // Attempt graceful stop
      if not Exec('sc.exe', 'stop {#MyServiceName}', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
      begin
        Result := 'Не удалось выполнить команду остановки службы sc.exe.';
        Exit;
      end;

      // Wait up to 30 seconds for SERVICE_STOPPED
      for I := 1 to 30 do
      begin
        Sleep(1000);
        if QueryServiceStateEx('{#MyServiceName}', SvcState, LastErr) then
        begin
          if SvcState = SERVICE_STOPPED then
            Break;
        end;
      end;

      if SvcState <> SERVICE_STOPPED then
      begin
        Result := CustomMessage('StopServiceTimeout');
      end;
    end;
  end
  else
  begin
    if LastErr <> ERROR_SERVICE_DOES_NOT_EXIST then
    begin
      Result := 'Ошибка обращения к диспетчеру служб Windows (код: ' + IntToStr(LastErr) + ').';
    end;
  end;
end;

procedure BrowseDbFolderClick(Sender: TObject);
var
  ChosenDir: string;
begin
  ChosenDir := EditOneDbPath.Text;
  if BrowseForFolder('Выберите каталог файловой базы POSCENTER ONE:', ChosenDir, False) then
  begin
    EditOneDbPath.Text := ChosenDir;
  end;
end;

procedure BrowseMappingFileClick(Sender: TObject);
var
  ChosenFile: string;
begin
  ChosenFile := EditMappingPath.Text;
  if GetOpenFileName('Выберите файл stage0_mapping.json', ChosenFile, '', 'Файлы JSON (*.json)|*.json|Все файлы (*.*)|*.*', 'json') then
  begin
    EditMappingPath.Text := ChosenFile;
  end;
end;

procedure InitializeWizard();
var
  LblCloudUrl, LblApiKey: TLabel;
  LblOneDbPath, LblOneUser, LblOnePass: TLabel;
  LblMappingPath, LblMappingInfo: TLabel;
  LblStateNotice: TLabel;
begin
  // --- Page 0 (Upgrade Only): Upgrade Choice ---
  PageUpgrade := CreateCustomPage(wpSelectDir, CustomMessage('UpgradePageTitle'), CustomMessage('UpgradePageDesc'));

  RadioKeepConfig := TRadioButton.Create(PageUpgrade);
  RadioKeepConfig.Parent := PageUpgrade.Surface;
  RadioKeepConfig.Caption := CustomMessage('UpgradeKeepConfig');
  RadioKeepConfig.Left := ScaleX(10);
  RadioKeepConfig.Top := ScaleY(15);
  RadioKeepConfig.Width := PageUpgrade.SurfaceWidth - ScaleX(20);
  RadioKeepConfig.Checked := True;

  RadioReconfigure := TRadioButton.Create(PageUpgrade);
  RadioReconfigure.Parent := PageUpgrade.Surface;
  RadioReconfigure.Caption := CustomMessage('UpgradeReconfigure');
  RadioReconfigure.Left := ScaleX(10);
  RadioReconfigure.Top := ScaleY(45);
  RadioReconfigure.Width := PageUpgrade.SurfaceWidth - ScaleX(20);

  // If agent_state.db exists, disallow reconfiguration in this version to avoid mixing client states
  if HasExistingStateDb then
  begin
    RadioKeepConfig.Checked := True;
    RadioReconfigure.Enabled := False;

    LblStateNotice := TLabel.Create(PageUpgrade);
    LblStateNotice.Parent := PageUpgrade.Surface;
    LblStateNotice.Caption := CustomMessage('ReconfigureBlockedDueToState');
    LblStateNotice.Left := ScaleX(10);
    LblStateNotice.Top := ScaleY(80);
    LblStateNotice.Width := PageUpgrade.SurfaceWidth - ScaleX(20);
    LblStateNotice.WordWrap := True;
    LblStateNotice.Font.Style := [fsBold];
  end;

  // --- Page 1: Cloud Settings ---
  PageCloud := CreateCustomPage(PageUpgrade.ID, CustomMessage('CloudPageTitle'), CustomMessage('CloudPageDesc'));

  LblCloudUrl := TLabel.Create(PageCloud);
  LblCloudUrl.Parent := PageCloud.Surface;
  LblCloudUrl.Caption := CustomMessage('CloudUrlLabel');
  LblCloudUrl.Left := ScaleX(0);
  LblCloudUrl.Top := ScaleY(10);

  EditCloudUrl := TNewEdit.Create(PageCloud);
  EditCloudUrl.Parent := PageCloud.Surface;
  EditCloudUrl.Text := 'https://api.cashback-qr.poscenter.kz';
  EditCloudUrl.Left := ScaleX(0);
  EditCloudUrl.Top := ScaleY(28);
  EditCloudUrl.Width := PageCloud.SurfaceWidth;

  LblApiKey := TLabel.Create(PageCloud);
  LblApiKey.Parent := PageCloud.Surface;
  LblApiKey.Caption := CustomMessage('ApiKeyLabel');
  LblApiKey.Left := ScaleX(0);
  LblApiKey.Top := ScaleY(65);

  EditApiKey := TNewEdit.Create(PageCloud);
  EditApiKey.Parent := PageCloud.Surface;
  EditApiKey.PasswordChar := '*';
  EditApiKey.Left := ScaleX(0);
  EditApiKey.Top := ScaleY(83);
  EditApiKey.Width := PageCloud.SurfaceWidth;

  // --- Page 2: 1C Connection Settings ---
  PageOne := CreateCustomPage(PageCloud.ID, CustomMessage('OnePageTitle'), CustomMessage('OnePageDesc'));

  LblOneDbPath := TLabel.Create(PageOne);
  LblOneDbPath.Parent := PageOne.Surface;
  LblOneDbPath.Caption := CustomMessage('OneDbPathLabel');
  LblOneDbPath.Left := ScaleX(0);
  LblOneDbPath.Top := ScaleY(10);

  EditOneDbPath := TNewEdit.Create(PageOne);
  EditOneDbPath.Parent := PageOne.Surface;
  EditOneDbPath.Left := ScaleX(0);
  EditOneDbPath.Top := ScaleY(28);
  EditOneDbPath.Width := PageOne.SurfaceWidth - ScaleX(85);

  BtnBrowseDb := TNewButton.Create(PageOne);
  BtnBrowseDb.Parent := PageOne.Surface;
  BtnBrowseDb.Caption := 'Обзор...';
  BtnBrowseDb.Left := PageOne.SurfaceWidth - ScaleX(80);
  BtnBrowseDb.Top := ScaleY(27);
  BtnBrowseDb.Width := ScaleX(80);
  BtnBrowseDb.OnClick := @BrowseDbFolderClick;

  LblOneUser := TLabel.Create(PageOne);
  LblOneUser.Parent := PageOne.Surface;
  LblOneUser.Caption := CustomMessage('OneUserLabel');
  LblOneUser.Left := ScaleX(0);
  LblOneUser.Top := ScaleY(65);

  EditOneUser := TNewEdit.Create(PageOne);
  EditOneUser.Parent := PageOne.Surface;
  EditOneUser.Text := 'loyalty_ro';
  EditOneUser.Left := ScaleX(0);
  EditOneUser.Top := ScaleY(83);
  EditOneUser.Width := PageOne.SurfaceWidth;

  LblOnePass := TLabel.Create(PageOne);
  LblOnePass.Parent := PageOne.Surface;
  LblOnePass.Caption := CustomMessage('OnePassLabel');
  LblOnePass.Left := ScaleX(0);
  LblOnePass.Top := ScaleY(120);

  EditOnePass := TNewEdit.Create(PageOne);
  EditOnePass.Parent := PageOne.Surface;
  EditOnePass.PasswordChar := '*';
  EditOnePass.Left := ScaleX(0);
  EditOnePass.Top := ScaleY(138);
  EditOnePass.Width := PageOne.SurfaceWidth;

  // --- Page 3: Mapping Settings ---
  PageMapping := CreateCustomPage(PageOne.ID, CustomMessage('MappingPageTitle'), CustomMessage('MappingPageDesc'));

  LblMappingPath := TLabel.Create(PageMapping);
  LblMappingPath.Parent := PageMapping.Surface;
  LblMappingPath.Caption := CustomMessage('MappingFileLabel');
  LblMappingPath.Left := ScaleX(0);
  LblMappingPath.Top := ScaleY(10);

  EditMappingPath := TNewEdit.Create(PageMapping);
  EditMappingPath.Parent := PageMapping.Surface;
  EditMappingPath.Left := ScaleX(0);
  EditMappingPath.Top := ScaleY(28);
  EditMappingPath.Width := PageMapping.SurfaceWidth - ScaleX(85);

  BtnBrowseMapping := TNewButton.Create(PageMapping);
  BtnBrowseMapping.Parent := PageMapping.Surface;
  BtnBrowseMapping.Caption := 'Обзор...';
  BtnBrowseMapping.Left := PageMapping.SurfaceWidth - ScaleX(80);
  BtnBrowseMapping.Top := ScaleY(27);
  BtnBrowseMapping.Width := ScaleX(80);
  BtnBrowseMapping.OnClick := @BrowseMappingFileClick;

  LblMappingInfo := TLabel.Create(PageMapping);
  LblMappingInfo.Parent := PageMapping.Surface;
  LblMappingInfo.Caption := CustomMessage('MappingInfo');
  LblMappingInfo.Left := ScaleX(0);
  LblMappingInfo.Top := ScaleY(75);
  LblMappingInfo.Width := PageMapping.SurfaceWidth;
  LblMappingInfo.WordWrap := True;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;

  if PageID = PageUpgrade.ID then
  begin
    // Only show upgrade choice if .env.service already exists
    Result := not IsUpgradeMode;
    Exit;
  end;

  if (PageID = PageCloud.ID) or (PageID = PageOne.ID) or (PageID = PageMapping.ID) then
  begin
    // Skip configuration pages if updating and user chose to keep existing settings
    if IsUpgradeMode and RadioKeepConfig.Checked then
    begin
      Result := True;
      Exit;
    end;
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  UrlClean: string;
  StateDbPath: string;
begin
  Result := True;

  if CurPageID = PageUpgrade.ID then
  begin
    StateDbPath := ExpandConstant('{commonappdata}\POSCENTER\LoyaltyAgent\state\agent_state.db');
    if RadioReconfigure.Checked and FileExists(StateDbPath) then
    begin
      MsgBox(CustomMessage('ReconfigureBlockedDueToState'), mbError, MB_OK);
      Result := False;
      Exit;
    end;
  end;

  if CurPageID = PageCloud.ID then
  begin
    UrlClean := Trim(EditCloudUrl.Text);
    if UrlClean = '' then
    begin
      MsgBox('Адрес облака не может быть пустым.', mbError, MB_OK);
      Result := False;
      Exit;
    end;
    if Copy(Lowercase(UrlClean), 1, 8) <> 'https://' then
    begin
      MsgBox('Адрес облака в production обязан использовать защищённый протокол HTTPS (https://...).', mbError, MB_OK);
      Result := False;
      Exit;
    end;
    if not CheckDisallowedInput('Адрес облака', UrlClean) then
    begin
      Result := False;
      Exit;
    end;

    if Trim(EditApiKey.Text) = '' then
    begin
      MsgBox('Введите ключ агента (Agent API Key). Без ключа авторизация в облаке невозможна.', mbError, MB_OK);
      Result := False;
      Exit;
    end;
    if Length(Trim(EditApiKey.Text)) < 16 then
    begin
      MsgBox('Ключ агента в production должен содержать не менее 16 символов.', mbError, MB_OK);
      Result := False;
      Exit;
    end;
    if not CheckDisallowedInput('Ключ агента', Trim(EditApiKey.Text)) then
    begin
      Result := False;
      Exit;
    end;
  end;

  if CurPageID = PageOne.ID then
  begin
    if Trim(EditOneDbPath.Text) = '' then
    begin
      MsgBox('Укажите путь к каталогу файловой базы данных 1С.', mbError, MB_OK);
      Result := False;
      Exit;
    end;
    if not DirExists(Trim(EditOneDbPath.Text)) then
    begin
      MsgBox('Указанный каталог базы данных 1С не существует.', mbError, MB_OK);
      Result := False;
      Exit;
    end;
    if not CheckDisallowedInput('Каталог базы 1С', Trim(EditOneDbPath.Text)) then
    begin
      Result := False;
      Exit;
    end;

    if not CheckDisallowedInput('Пользователь 1С', Trim(EditOneUser.Text)) then
    begin
      Result := False;
      Exit;
    end;

    if not CheckDisallowedInput('Пароль 1С', EditOnePass.Text) then
    begin
      Result := False;
      Exit;
    end;
  end;

  if CurPageID = PageMapping.ID then
  begin
    if (not IsUpgradeMode) and (Trim(EditMappingPath.Text) = '') then
    begin
      MsgBox('Для первичной установки обязателен подтверждённый файл маппинга (stage0_mapping.json). Агент не угадывает структуру базы 1С.', mbError, MB_OK);
      Result := False;
      Exit;
    end;

    if (Trim(EditMappingPath.Text) <> '') and (not FileExists(Trim(EditMappingPath.Text))) then
    begin
      MsgBox('Указанный файл маппинга не найден на диске.', mbError, MB_OK);
      Result := False;
      Exit;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  DataDir, ConfigDir, StateDir, LogsDir, MappingDir: string;
  EnvFile, StateKeyFile, StateDbFile: string;
  ResultCode, I: Integer;
  AppExe: string;
  MappingSrc, ExistingMapping: string;
  NeedsConfigWrite: Boolean;
  SvcState, LastErr: DWORD;
begin
  if CurStep = ssPostInstall then
  begin
    AppExe := ExpandConstant('{app}\{#MyAppExeName}');
    DataDir := ExpandConstant('{commonappdata}\POSCENTER\LoyaltyAgent');
    ConfigDir := DataDir + '\config';
    StateDir := DataDir + '\state';
    LogsDir := DataDir + '\logs';
    MappingDir := DataDir + '\mapping';
    EnvFile := ConfigDir + '\.env.service';
    StateKeyFile := StateDir + '\agent_state.key';
    StateDbFile := StateDir + '\agent_state.db';

    NeedsConfigWrite := (not IsUpgradeMode) or RadioReconfigure.Checked;

    // Safety guard: if state DB exists, reconfigure is forbidden in this version
    if NeedsConfigWrite and FileExists(StateDbFile) then
      RaiseException(CustomMessage('ReconfigureBlockedDueToState'));

    // 1. Create directories with error checking
    if not ForceDirectories(ConfigDir) then
      RaiseException('Ошибка создания каталога конфигурации: ' + ConfigDir);
    if not ForceDirectories(StateDir) then
      RaiseException('Ошибка создания каталога состояния: ' + StateDir);
    if not ForceDirectories(LogsDir) then
      RaiseException('Ошибка создания каталога логов: ' + LogsDir);
    if not ForceDirectories(MappingDir) then
      RaiseException('Ошибка создания каталога маппинга: ' + MappingDir);

    // 2. Protect config and state directories BEFORE writing secrets (SID: SYSTEM=*S-1-5-18, Admins=*S-1-5-32-544)
    if not SecureDirectoryAcl(ConfigDir) then
      RaiseException(CustomMessage('AclFailed') + ' (Каталог: ' + ConfigDir + ')');
    if not SecureDirectoryAcl(StateDir) then
      RaiseException(CustomMessage('AclFailed') + ' (Каталог: ' + StateDir + ')');

    // 3. Protect existing sensitive files BEFORE writing or updating secrets
    if FileExists(EnvFile) then
    begin
      if not SecureFileAcl(EnvFile) then
        RaiseException(CustomMessage('AclFailed') + ' (Файл: ' + EnvFile + ')');
    end;
    if FileExists(StateKeyFile) then
    begin
      if not SecureFileAcl(StateKeyFile) then
        RaiseException(CustomMessage('AclFailed') + ' (Файл: ' + StateKeyFile + ')');
    end;

    // 4. Mapping validation and setup
    if NeedsConfigWrite then
    begin
      MappingSrc := Trim(EditMappingPath.Text);
      if (MappingSrc <> '') and FileExists(MappingSrc) then
      begin
        // Validate mapping with agent binary before proceeding!
        if not Exec(AppExe, 'stage0 validate-mapping "' + MappingSrc + '" --require-verified', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
          RaiseException('Не удалось запустить валидатор маппинга: ' + AppExe);

        if ResultCode <> 0 then
          RaiseException(CustomMessage('MappingValidationFailed') + ' (Код завершения: ' + IntToStr(ResultCode) + ')');

        if not CopyFile(MappingSrc, MappingDir + '\stage0_mapping.json', False) then
          RaiseException('Ошибка копирования файла маппинга в: ' + MappingDir);
      end;
    end
    else
    begin
      // In upgrade mode with preserved config: validate existing mapping file!
      ExistingMapping := MappingDir + '\stage0_mapping.json';
      if not FileExists(ExistingMapping) then
        RaiseException('Файл маппинга отсутствует: ' + ExistingMapping + '. Запустите установщик с выбором изменения настроек для указания файла маппинга.');

      if not Exec(AppExe, 'stage0 validate-mapping "' + ExistingMapping + '" --require-verified', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
        RaiseException('Не удалось запустить валидатор существующего маппинга: ' + AppExe);

      if ResultCode <> 0 then
        RaiseException(CustomMessage('MappingValidationFailed') + ' (Существующий маппинг не прошёл проверку, код: ' + IntToStr(ResultCode) + ')');
    end;

    // 5. Write .env.service if new install or reconfigure chosen
    if NeedsConfigWrite then
    begin
      if not SerializeConfigToFile(EnvFile, Trim(EditCloudUrl.Text), Trim(EditApiKey.Text), Trim(EditOneDbPath.Text), Trim(EditOneUser.Text), EditOnePass.Text) then
        RaiseException('Ошибка записи файла конфигурации: ' + EnvFile);

      // Tighten ACL on the written file
      if not SecureFileAcl(EnvFile) then
        RaiseException(CustomMessage('AclFailed') + ' (Файл: ' + EnvFile + ')');
    end;

    // 6. Windows Service Registration via agent binary
    if not Exec(AppExe, 'service install', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
      RaiseException('Не удалось запустить команду регистрации службы: ' + AppExe);

    if ResultCode <> 0 then
      RaiseException(CustomMessage('ServiceInstallFailed') + ' (Код завершения: ' + IntToStr(ResultCode) + ')');

    // Configure service parameters: delayed-auto and failure recovery
    if not Exec('sc.exe', 'config {#MyServiceName} start= delayed-auto', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
      RaiseException('Не удалось настроить запуск службы sc.exe config');
    if ResultCode <> 0 then
      RaiseException('Ошибка настройки запуска службы sc.exe config (код: ' + IntToStr(ResultCode) + ')');

    if not Exec('sc.exe', 'failure {#MyServiceName} reset= 86400 actions= restart/60000/restart/300000/restart/900000', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
      RaiseException('Не удалось настроить перезапуск службы sc.exe failure');
    if ResultCode <> 0 then
      RaiseException('Ошибка настройки перезапуска службы sc.exe failure (код: ' + IntToStr(ResultCode) + ')');

    if not Exec('sc.exe', 'description {#MyServiceName} "Background synchronization service for POSCENTER Loyalty system."', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
      RaiseException('Не удалось задать описание службы sc.exe description');
    if ResultCode <> 0 then
      RaiseException('Ошибка задания описания службы sc.exe description (код: ' + IntToStr(ResultCode) + ')');

    // 7. Start service and wait for RUNNING
    if not Exec('sc.exe', 'start {#MyServiceName}', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
      RaiseException('Не удалось запустить службу: ошибка вызова sc.exe start');
    if (ResultCode <> 0) and (ResultCode <> 1056) then
      RaiseException('Ошибка вызова sc.exe start (код: ' + IntToStr(ResultCode) + ')');

    SvcState := 0;
    for I := 1 to 15 do
    begin
      Sleep(1000);
      if QueryServiceStateEx('{#MyServiceName}', SvcState, LastErr) then
      begin
        if SvcState = SERVICE_RUNNING then
          Break;
      end;
    end;

    if SvcState = SERVICE_RUNNING then
    begin
      MsgBox(CustomMessage('ServiceRunningNotice'), mbInformation, MB_OK);
    end
    else
    begin
      RaiseException(CustomMessage('ServiceStartTimeout') + ' (Состояние службы: ' + IntToStr(SvcState) + ')');
    end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode, I: Integer;
  DataDir, ConfigFile: string;
  SvcState, LastErr: DWORD;
begin
  if CurUninstallStep = usUninstall then
  begin
    // 1. Check service existence and stop if running
    if QueryServiceStateEx('{#MyServiceName}', SvcState, LastErr) then
    begin
      if (SvcState <> 0) and (SvcState <> SERVICE_STOPPED) then
      begin
        if not Exec('sc.exe', 'stop {#MyServiceName}', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
          RaiseException('Не удалось вызвать команду остановки службы sc.exe stop');

        for I := 1 to 30 do
        begin
          Sleep(1000);
          if QueryServiceStateEx('{#MyServiceName}', SvcState, LastErr) then
          begin
            if SvcState = SERVICE_STOPPED then
              Break;
          end;
        end;

        if SvcState <> SERVICE_STOPPED then
          RaiseException('Не удалось остановить службу {#MyServiceName} перед удалением (превышено время ожидания 30 сек). Деинсталляция прервана.');
      end;

      // 2. Delete Windows Service and verify
      if not Exec('sc.exe', 'delete {#MyServiceName}', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
        RaiseException('Не удалось выполнить sc.exe delete {#MyServiceName}');
      if (ResultCode <> 0) and (ResultCode <> 1060) then
        RaiseException('Ошибка удаления службы sc.exe delete (код: ' + IntToStr(ResultCode) + ')');
    end
    else
    begin
      if LastErr <> ERROR_SERVICE_DOES_NOT_EXIST then
        RaiseException('Ошибка обращения к диспетчеру служб Windows (код: ' + IntToStr(LastErr) + '). Деинсталляция прервана.');
    end;
  end;

  if CurUninstallStep = usPostUninstall then
  begin
    // By default: KEEP all data, logs, state DB, state key, mapping!
    // Offer optional deletion of .env.service secrets only
    DataDir := ExpandConstant('{commonappdata}\POSCENTER\LoyaltyAgent');
    ConfigFile := DataDir + '\config\.env.service';

    if FileExists(ConfigFile) then
    begin
      if MsgBox(CustomMessage('PurgeSecretsPrompt'), mbConfirmation, MB_YESNO) = idYes then
      begin
        DeleteFile(ConfigFile);
        // Note: HMAC key (agent_state.key) and SQLite state DB are KEPT TOGETHER to avoid breaking hash continuity.
      end;
    end;
  end;
end;
