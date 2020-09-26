PLUGIN_PATH="$HOME/.local/share/krunner/plugin/miSecretService/"

echo "Put plugin in: $PLUGIN_PATH"
mkdir -p "$PLUGIN_PATH"
cp secret.py "$PLUGIN_PATH"
cp clipboard.py "$PLUGIN_PATH"
cp krunner.py "$PLUGIN_PATH"
cp miSecretService.py "$PLUGIN_PATH"
chmod u+x "$PLUGIN_PATH/miSecretService.py"

AUTOSTART_PATH="$HOME/.config/autostart/"
echo "Enable in autostart: $AUTOSTART_PATH"
mkdir -p "$AUTOSTART_PATH"
cp miSecretService-autostart.desktop "$AUTOSTART_PATH"

KSERVICE_PATH="$HOME/.local/share/kservices5/"
echo "Enable in kservice5: $KSERVICE_PATH"
mkdir -p "$KSERVICE_PATH"
cp plasma-runner-miSecretService.desktop "$KSERVICE_PATH"

echo "Stopping old miSecretService (if any)"
killall miSecretService.py

echo "Launching service miSecretService"
(cd $PLUGIN_PATH; nohup ./miSecretService.py &)
echo "(log under $PLUGIN_PATH/nohup.out)"

echo "Killing krunner to read in new configuration"
killall krunner  # starts automagically
