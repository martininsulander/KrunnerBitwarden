
# KrunnerBitwarden

A Bitwarden runner for KDE Plasma Krunner in python.

The program is a bridge that connects the bitwarden cli program with krunner.
It is autostarted by kde.

Use until all get their acts together and support a common standard for
password management (f.ex. https://specifications.freedesktop.org/secret-service/).

If you use f.ex. Keepass, check the krunner
https://github.com/martininsulander/KrunnerSecretService

## Usage
To use, write in krunner "pass {one or more letters}" to 
list matching passwords.

At first start, after sleep or a long time without using
the computer, there will be a unlock choise instead.

## Install
Run install.sh to install it locally.

Make sure you have bitwarden cli installed and runnable as ''bw''.

In Krunner, enable "Bitwarden" program.

### Requires

Bwcli installation (with 'bw' in path)

kdialog for password

python3 with the following modules

* dbus
* gi (from Glib)

