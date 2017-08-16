#

# Path to store PID files

# This does not need to persist between reboots, as it only contains information about running
# unison instances. Typically easiest to mount somewhere in /var/run
data_dir = '/var/run/unisonctl'

# Directory where the unison configuration files are stored
unison_config_dir = '/var/run/unisonctl'

# Directory where the unison configuration file templates are stored
unison_config_template_dir = '/opt/unison/config/templates'


# Important directories - these will get their own unison instances to speed up replication

# NOTE: Order matters. The rules are run in sequential order. Each rule can only capture
# files not already captured in a previous rule, to ensure that syncs don't overlap,
# unless the 'overlap' paramater is set to true.

sync_hierarchy_rules = [

    # Sync the 3 highest-counted folders starting with '11' in their own unison instance
    {
        # Name of the unison profile which will be created
        # can be any alphanumeric string (a-z, A-Z, 1-9) to identify the sync
        'syncname':'',

        # Select the directories which will be synced with this profile
        # Use standard shell globbing to select files from the root directory
        # TODO: rewrite that wording
        'dir_filter':'11*',

        # Select a method to sort the files
        # Current options:
        #   name_highfirst
        #   name_highfirst
        #   creation_date_highfirst
        #   creation_date_lowfirst
        'method':'int_sort_high_low',
        # Select X from the top of the list you sorted above
        'method_param':3
    },

    # Sync the 6 highest-counted folders starting with '11' in their own unison instance
    {
        'dir_filter':'11*',
        'method':'int_sort_high_low',
        'method_param':6
    },

    # Sync the 3 highest-counted folders starting with "O" in their own unison instance
    {
        'dir_filter':'O*',
        'method':'int_sort_high_low',
        'method_param':3
    },

    # Sync any files not caught above in their own instance
    {
        'dir_filter':'*',
        'overlap':True
    },

]

# Log file
# log_file = '/opt/unison/config/templates'
# log_file = '/opt/unison/config/templates'

# If set to true, directories will be made if the paths are not found on the system
# If set to false, program will return an error if the directories do not exist
make_root_directories_if_not_found = True
