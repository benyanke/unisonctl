#!/usr/bin/env python3

# Unison control script
#
# This script handles the file-based data storage
#

# TODO: Replace DEBUG var with an actual logging framework, including log level

import subprocess
import os
import glob
import atexit
import itertools
import hashlib
import time
import psutil
import signal

from datastorage import DataStorage


class UnisonHandler():
    """Starts, stops and monitors unison instances."""

    # Object for data storage backend
    data_storage = None

    # configuration values
    config = {}

    # Enables extra output
    DEBUG = True

    def __init__(self, debug=DEBUG):
        """Prepare UnisonHandler to manage unison instances.

        Parameters
        ----------
        none

        Returns
        -------
        null

        Throws
        -------
        none

        Doctests
        -------

        """
        # Register exit handler
        atexit.register(self.exit_handler)

        # Handle manual debug setting
        self.DEBUG = debug

        # Set up configuration
        self.import_config()

        # Set up data storage backend
        self.data_storage = DataStorage(self.DEBUG, self.config)

        if(self.DEBUG):
            print("Constructor complete")
            self.create_all_sync_instances()
    """

    # Algo required

    commands:

    unisonctrl status-not sure, maybe combine with list

    unisonctrl list-list currently running unison instances by reading pidfiles
    and perhaps:
        - confirming they're still running (pidcheck, simple)
        - confirming they're not stuck (logs? pid communicaton?)
        - when was last loop? (logs? wrapper script?)

    unisonctrl update-check directory structure and make sure rules don't need
    to be changed because of a change or

    unisonctrl restart-stop + start

    unisonctrl stop-stop all running unison instances, delete files in tmp dir

    unisonctrl start-recalculate directory structure and regenerate config
    files, restart unison instances


    other features not sure where to put:/public/img should work, and is not
    caught by .gitignore

        # Get the
     * check for unexpected dead processes and check logs
     * parse logs and send stats to webhook
     * calculate average sync latency

    """

    def create_all_sync_instances(self):
        """Create multiple sync instances from the config and filesystem info.

        Parameters
        ----------
        none

        Returns
        -------
        list
            PIDs of dead unison instances which we thought were running.

        Throws
        -------
        none

        """
        dirs_to_sync_by_sync_instance = self.get_dirs_to_sync(self.config['sync_hierarchy_rules'])

        # Loop through each entry in the dict and create a sync instance for it
        for instance_name, dirs_to_sync in dirs_to_sync_by_sync_instance.items():
            self.create_sync_instance(instance_name, dirs_to_sync)

    def get_dirs_to_sync(self, sync_hierarchy_rules):
        """Start a new sync instance with provided details.

        # Parses the filesystem, and lists l

        Parameters
        ----------
        Pass through sync_hierarchy_rules from config

        Returns
        -------
        dict (nested)
            [syncname] - name of the sync name for this batch
                ['sync'] - directories to sync in this instance
                ['ignore'] - directories to ignore in this instance

        Throws
        -------
        none

        """
        # contains the list of directories which have been handled by the loop
        # so future iterations don't duplicate work
        handled_dirs = []

        # Contains list which is built up within the loop and returned at the
        # end of the method
        all_dirs_to_sync = {}

        for sync_instance in sync_hierarchy_rules:

            # Find full list
            expr = (
                self.config['unison_local_root'] +
                os.sep +
                sync_instance['dir_selector']
            )

            # Get full list of glob directories
            all_dirs_from_glob = glob.glob(self.sanatize_path(expr))

            # Remove any dirs already handled in a previous loop, unless
            # overlap is set
            if (
                'overlap' not in sync_instance or
                sync_instance['overlap'] is False
            ):
                print("NO OVERLAP ALLOWED")
                before = len(all_dirs_from_glob)
                all_unhandled_dirs_from_glob = [x for x in all_dirs_from_glob if x not in handled_dirs]
                after = len(all_unhandled_dirs_from_glob)

                if(self.DEBUG and before != after):
                    print(str(before) + " down to " + str(after) + " by removing already handled dirs")

            # By default, use 'name_highfirst'
            if 'sort_method' not in sync_instance:
                sync_instance['sort_method'] = 'name_highfirst'

            # Apply sort
            if sync_instance['sort_method'] == 'name_highfirst':
                sorted_dirs = sorted(all_unhandled_dirs_from_glob, reverse=True)
            elif sync_instance['sort_method'] == 'name_lowfirst':
                sorted_dirs = sorted(all_unhandled_dirs_from_glob)
            # Add other sort implementations here
            else:
                raise ValueError(
                    sync_instance['sort_method'] +
                    " is not a valid sort method on sync instance " +
                    sync_instance['syncname']
                )

            # Apply sort_count_offet
            if 'sort_count_offet' in sync_instance:
                if(self.DEBUG):
                    print("OFFSET SET FOR " + sync_instance['syncname'])
                del sorted_dirs[:sync_instance['sort_count_offet']]

            # Apply sort_count
            if 'sort_count' in sync_instance:
                if(self.DEBUG):
                    print("COUNT SET FOR " + sync_instance['syncname'])
                dirs_to_sync = list(itertools.islice(sorted_dirs, 0, sync_instance['sort_count'], 1))
            else:
                dirs_to_sync = sorted_dirs

            # Add all these directories to the handled_dirs so they aren't
            # duplicated later
            handled_dirs += dirs_to_sync

            # add dirs to final output nested dict
            if len(dirs_to_sync) > 0:
                all_dirs_to_sync[sync_instance['syncname']] = dirs_to_sync

            if(self.DEBUG):
                dirstr = "\n   ".join(dirs_to_sync)
                print(
                    sync_instance['syncname'] +
                    " directories :\n   " +
                    dirstr + "\n\n"
                )

        if(self.DEBUG):
            print("All directories synced :\n   " + "\n   ".join(handled_dirs))

        return all_dirs_to_sync

    def create_sync_instance(self, instance_name, dirs_to_sync):
        """Start a new sync instance with provided details, if not already there.

        Parameters
        ----------
        dict
            List of directories to sync with each instance. The key of the dict
            becomes the name of the sync instance. The value of the dict
            becomes the list of directories to sync with that instance.

        Returns
        -------
        list
            PIDs of dead unison instances which we thought were running.

        Throws
        -------
        none

        """
        # Obtain a hash of the requested config to be able to later check if
        # the instance should be killed and restarted or not
        config_hash = hashlib.sha256((str(instance_name) + str(dirs_to_sync)).encode('utf-8')).hexdigest()

        # Get data from requested instance, if there is any
        requested_instance = self.data_storage.get_data(instance_name)

        if requested_instance is None:
            # No instance data found, must start new one
            if(self.DEBUG):
                print("No instance data found for " + instance_name + ", must start new one")
        elif requested_instance['config_hash'] == config_hash:
            # Existing instance data found, still uses same config - no restart
            if(self.DEBUG):
                print("Instance data found for " + instance_name + " - still using same config, no need to restart")
            return
        else:
            # Existing instance data found, but uses different config, so restarting
            if(self.DEBUG):
                print("Instance data found for " + instance_name + " - using different config, killing and restarting")

        # self.kill_instance_by_pid(requested_instance['pid'])
        self.kill_instance_by_pid(8408)


# proc = Popen([cmd_str], shell=True,
#             stdin=None, stdout=None, stderr=None, close_fds=True)
        # If reached here, a new instance is needed and the current one is dead
        # or otherwise not in existance

    def kill_instance_by_pid(self, pid):
        """Kill unison instance by PID.

        Includes build in protection for accidentally killing a non-unison
        program, and even other unison programs not started with this script

        Paramaters
        -------
        int
            pid to kill - must be a PID started in this process

        Throws
        -------
        none

        Returns
        -------
        none

        Throws
        -------
        none

        Doctests
        -------

        """
        # Get the list of known pids to ensure we only kill one of those
        running_data = self.data_storage.running_data
        # print(running_data)

        known_pids = []

        # TODO: Rewrite this function, it can probably be done with reduce()
        # Gets PIDs of all the known unison processes
        for entry in running_data:
            running_data[entry]
            known_pids.append(int(running_data[entry]['pid']))

        # TODO: Finish this error checking logic here, currently it doesn't check the PID

        # Try and kill with sigint (same as ctrl+c)
        if pid not in known_pids:
            msg = "Process ID:" + str(pid) + " is not in our list of known PIDs - refusing to kill"
            raise RuntimeError(msg)
        else:
            os.kill(pid, signal.SIGINT)

        # Keep checkig to see if dead yet
        for _ in range(20):

            if psutil.pid_exists(pid):
                # If still alive, keep waiting and try again
                time.sleep(.300)
            else:
                # If dead, exit function
                return

        # If not dead after checks above, kill more aggressively
        # TODO: fill in here

    def find_dead_processes(self):
        """Ensure all expected processes are still running.

        Checks the running_data list against the current PID list to ensure
        all expected processes are still running.

        Parameters
        ----------
        none

        Returns
        -------
        list
            PIDs of dead unison instances which we thought were running.

        Throws
        -------
        none

        """
        # Set some tmp data
        self.data_storage.set_data("key", {"pid": 11110, "syncname": "key0"})

        # Get the list of processes we know are running and we think are running
        actually_running_processes = self.get_running_unison_processes()
        supposedly_running_processes = self.data_storage.running_data
        print(supposedly_running_processes)
        dead_pids = list(
            set(supposedly_running_processes) - set(actually_running_processes)
        )

        print(dead_pids)

        # TODO: Handle these

    def get_running_unison_processes(self):
        """Return PIDs of currently running unison instances.

        Parameters
        ----------
        none

        Returns
        -------
        list
            PIDs of unison instances, empty list

        Throws
        -------
        none

        """
        # Get PIDs
        # Note: throws exception if no instances exist
        try:
            pids = str(subprocess.check_output(["pidof", 'unison']))

            # Parse command output into list by removing junk chars and exploding
            # string with space delimiter
            pids = pids[2:-3].split(' ')

        except subprocess.CalledProcessError:
            # If error caught here, no unison instances are found running
            pids = []

        if self.DEBUG:
            print("Found " + str(len(pids)) + " running instances on this system: " + str(pids))

        return pids

    def import_config(self):
        """Import config from config, and apply details where needed.

        Parameters
        ----------
        none

        Returns
        -------
        null

        Throws
        -------
            'LookupError' if config is invalid.

        """
        # Get the config file
        import config

        # Get all keys from keyvalue pairs in the config file
        settingsFromConfigFile = [x for x in dir(config) if not x.startswith('__')]

        # Settings validation: specify keys which are valid settings
        # If there are rows in the config file which are not listed here, an
        # error will be raised
        validSettings = {
            'unison_config_template_dir',
            'unison_config_dir',
            'data_dir',
            'log_file',
            'make_root_directories_if_not_found',
            'sync_hierarchy_rules',
            'unison_local_root',
            'unison_remote_root',
            'unison_path',
        }

        # If a setting contains a directory path, add it's key here and it will
        # be sanatized (whitespace and trailing whitespaces stripped)
        settingPathsToSanitize = {
            'unison_config_template_dir',
            'unison_config_dir',
            'data_dir',
        }

        # Values here are used as config values unless overridden in the
        # config.py file
        defaultSettings = {
            'data_dir': '/var/run/unisonctrld',
            'log_file': '/dev/null',
            'make_root_directories_if_not_found': True,
            'unison_path': '/usr/bin/unison',  # Default ubuntu path for unison
        }

        # Convert config file into dict
        for key in settingsFromConfigFile:
            value = getattr(config, key)
            self.config[key] = value

        # Apply default settings to fill gaps between explicitly set ones
        for key in defaultSettings:
            if (key not in self.config):
                self.config[key] = defaultSettings[key].strip()

        # Ensure all required keys are specified
        for key in validSettings:
            if (key not in self.config):
                raise LookupError("Required config entry '" + key + "' not specified")

        # Ensure no additional keys are specified
        for key in self.config:
            if (key not in validSettings):
                raise LookupError("Unknown config entry: '" + key + "'")

        # Sanatize directory paths
        for key in settingPathsToSanitize:
            self.config[key] = self.sanatize_path(self.config[key])

        # A few hardcoded config values
        self.config['data_dir'] = self.config['data_dir'] + os.sep + "running-sync-instances"

        # If you reach here, configuration was read without error.
        return

    def sanatize_path(self, path):
        """Sanitize directory paths by removing whitespace and trailing slashes.

        Currently only tested on Unix, but should also work on Windows.
        TODO: Test on windows to ensure it works properly.

        Parameters
        ----------
        1) str
            directory path to sanatize

        Returns
        -------
        str
            sanatized directory path

        Throws
        -------
        none

        Doctests
        -------
        >>> US = UnisonHandler(False)

        >>> US.sanatize_path(" /extra/whitespace ")
        '/extra/whitespace'

        >>> US.sanatize_path("/dir/with/trailing/slash/")
        '/dir/with/trailing/slash'

        >>> US.sanatize_path("  /dir/with/trailing/slash/and/whitepace/   ")
        '/dir/with/trailing/slash/and/whitepace'

        >>> US.sanatize_path("  /dir/with/many/trailing/slashes////   ")
        '/dir/with/many/trailing/slashes'

        """
        # Remove extra whitespace
        path = path.strip()

        # Remove slash from end of path
        path = path.rstrip(os.sep)

        return path

    def exit_handler(self):
        """Is called on exit automatically.

        Paramaters
        -------
        none

        Throws
        -------
        none

        Returns
        -------
        none

        Throws
        -------
        none

        Doctests
        -------

        """
        if(self.DEBUG):
            print(
                "Starting script shutdown in the class " +
                self.__class__.__name__
            )

        if(self.DEBUG):
            print(
                "Script shutdown complete in class " +
                self.__class__.__name__
            )


# tmp : make this more robust
US = UnisonHandler(True)
US.get_running_unison_processes()
