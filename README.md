# KrunnerSecretService
Secret Service runner for KDE Plasma Krunner in python

The program is a bridge that connects to krunner and keepassxc.
It is autostarted by kde.

## Usage
To use, write in krunner "pass {three or more letters}" to 
list matching passwords.

## Install
Run install.sh to install it locally.

In KeepassXC, check in settings that "Secret Service-integration"
is activated.

In Krunner, enable "Secret Service" program.

### Requires
python3 with the following modules

* secretstorage
* dbus
* gi (from Glib)
