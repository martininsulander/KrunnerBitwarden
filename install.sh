#!/bin/sh

# this would be for a root installation
# code paths for system installation
# CODE_PATH="/usr/share/krunner/dbusplugins/miSecretService/"
# KRUNNER_DBUSPLUGIN_PATH="/usr/share/krunner/dbusplugins/"
# KSERVICE_PATH="/usr/share/kservices5/krunner"
# dbus.service

if [ "$(id -u)" -eq 0 ]
then
  echo "Installation as root is not supported"
  exit 3
fi

CODE_PATH="$HOME/.local/share/krunner/plugin/miBwcli/"
KRUNNER_DBUSPLUGIN_PATH="$HOME/.local/share/krunner/dbusplugins/"
KSERVICE_PATH="$HOME/.local/share/kservices5/"
APP="mi_krunner_bwcli.py"
AUTOSTART_DESKTOP="mi-krunner-bwcli-autostart.desktop"
DBUS_PROCESS_ID="mi.bitwarden.krunner"

echo "Putting plugin in: $CODE_PATH"
mkdir -p "$CODE_PATH"
cp clipboard.py "$CODE_PATH"
cp bwcli.py "$CODE_PATH"
cp "$APP" "$CODE_PATH"
chmod u+x "$CODE_PATH/$APP"

USER_AUTOSTART_PATH="$HOME/.config/autostart/"
echo "Enable in autostart: $USER_AUTOSTART_PATH"
mkdir -p "$USER_AUTOSTART_PATH"
cp "$AUTOSTART_DESKTOP" "$USER_AUTOSTART_PATH"
sed -i "s+LOCATION+$CODE_PATH+g" "$USER_AUTOSTART_PATH/$AUTOSTART_DESKTOP"

echo "Enable in krunner: $KRUNNER_DBUSPLUGIN_PATH"
mkdir -p "$KRUNNER_DBUSPLUGIN_PATH"
cp plasma-runner-mi-bwcli.desktop "$KRUNNER_DBUSPLUGIN_PATH"

echo "Check for old $APP process"
oldpid=$(gdbus call --session --dest org.freedesktop.DBus --object-path / --method org.freedesktop.DBus.GetConnectionUnixProcessID $DBUS_PROCESS_ID | grep -oP " \K\d+") 2>/dev/null
if [ -n "$oldpid" ]; then
  echo "Stopping old $APP process"
  kill $oldpid
fi

echo "Launching service $APP"
(cd $CODE_PATH; nohup ./$APP &)
echo "(log under $CODE_PATH/nohup.out)"

echo "Killing krunner to read in new configuration"
killall krunner  # starts automagically
