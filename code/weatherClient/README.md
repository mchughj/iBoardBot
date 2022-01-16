
# Weather Client drives the update of the display with weather information

## Getting started

1. Install necessary prerequisites
   ```
   sudo apt install -y python3.7
   python3.7 -m pip install --user --upgrade pip
   python3.7 -m pip install --user virtualenv
   ```
1. Create a new virtual environment within this directory.
   ```
   python3.7 -m virtualenv --python=python3.7 env
   ```
1. Activate the new virtual environment
   ```
   source env/bin/activate
   ```
1. Install, into the new virtual environment, the required python modules for this specific environment.  This will be installed within the virtual env which was activated earlier.
   ```
   python3.7 -m pip install -r requirements.txt
   ```
1. Install the services
   ```
   ./install.sh
   ```

