"""Read-only FTPS connection check; credentials stay in an ignored local file."""
import ftplib
import ssl
import sys
from pathlib import Path


def main():
    path = Path(__file__).resolve().parents[1] / '.env.hosting.local'
    try:
        values = dict(line.split('=', 1) for line in path.read_text(encoding='utf-8-sig').splitlines()
                      if line.strip() and not line.lstrip().startswith('#') and '=' in line)
        context = ssl.create_default_context()
        # This hosting provider requires TLS 1.2 for reliable FTPS transfers.
        context.maximum_version = ssl.TLSVersion.TLSv1_2
        with ftplib.FTP_TLS(context=context, timeout=20) as ftp:
            ftp.connect(values['HOSTING_FTPS_HOST'], 21)
            ftp.login(values['HOSTING_FTPS_USER'], values['HOSTING_FTPS_PASSWORD'])
            ftp.prot_p()
            ftp.cwd(values['HOSTING_SITE_DIR'])
            names = {Path(name).name for name in ftp.nlst()}
            # NLST may hide dotfiles even when they exist.
            ftp.voidcmd('TYPE I')
            try:
                ftp.size('.htaccess')
                names.add('.htaccess')
            except ftplib.error_perm:
                pass
            print('FTPS_LOGIN_OK')
            print('SITE_DIRECTORY_OK')
            for name in ('index.html', '.htaccess', 'assets', 'demo', 'app'):
                print(name + ': ' + ('present' if name in names else 'absent'))
        return 0
    except ssl.SSLCertVerificationError:
        print('FTPS_CERTIFICATE_VERIFICATION_FAILED')
    except ftplib.error_perm as exc:
        print('FTPS_SERVER_ERROR_' + str(exc)[:3])
    except (OSError, ssl.SSLError, EOFError):
        print('FTPS_CONNECTION_FAILED')
    except (KeyError, ValueError):
        print('HOSTING_CONFIG_INVALID')
    return 1


if __name__ == '__main__':
    sys.exit(main())
