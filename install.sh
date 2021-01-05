#!/bin/sh

CODE_PATH="$HOME/.local/share/krunner/plugin/miSecretService/"
KRUNNER_DBUSPLUGIN_PATH="$HOME/.local/share/krunner/dbusplugins/"

echo "Putting plugin in: $CODE_PATH"
mkdir -p "$CODE_PATH"
cp secret.py "$CODE_PATH"
cp clipboard.py "$CODE_PATH"
cp krunner.py "$CODE_PATH"
cp miSecretService.py "$CODE_PATH"
chmod u+x "$CODE_PATH/miSecretService.py"

AUTOSTART_PATH="$HOME/.config/autostart/"
echo "Enable in autostart: $AUTOSTART_PATH"
mkdir -p "$AUTOSTART_PATH"
cp miSecretService-autostart.desktop "$AUTOSTART_PATH"

KSERVICE_PATH="$HOME/.local/share/kservices5/"
echo "Enable in krunner: $KRUNNER_DBUSPLUGIN_PATH"
mkdir -p "$KRUNNER_DBUSPLUGIN_PATH"
cp plasma-runner-miSecretService.desktop "$KRUNNER_DBUSPLUGIN_PATH"

echo "Check for old miSecretService process"
oldpid=$(gdbus call --session --dest org.freedesktop.DBus --object-path / --method org.freedesktop.DBus.GetConnectionUnixProcessID mi.secretservice.krunner | grep -oP " \K\d+") 2>/dev/null
if [ -n "$oldpid" ]; then
  echo "Stopping old miSecretService"
  kill $oldpid
fi

echo "Launching service miSecretService"
(cd $CODE_PATH; nohup ./miSecretService.py &)
echo "(log under $CODE_PATH/nohup.out)"

echo "Killing krunner to read in new configuration"
killall krunner  # starts automagically
