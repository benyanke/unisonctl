#

# Path to store PID files

# This does not need to persist between reboots, as it only contains information about running
# unison instances. Typically easiest to mount somewhere in /var/run
data_dir = '/var/run/unisonctrl'

# Directory where the unison configuration files are stored
unison_config_dir = '/var/run/unisonctrl'

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
        'syncname':'recent-phone-orders-batch1',

        # Select the directories which will be synced with this profile
        # Use standard shell globbing to select files from the root directory
        # TODO: rewrite that wording
        'dir_selector':'11*',

        # Select a method to sort the files
        # Current options:
        #   name_highfirst
        #   name_highfirst
        #   creation_date_highfirst
        #   creation_date_lowfirst
        'sort_method':'name_highfirst',
        # Select X from the top of the list you sorted above
        'sort_count':3,
    },

# 6cKMoYo$

    # Sync the 3 highest-counted folders starting with '11' in their own unison instance
    {
        'syncname':'recent-phone-orders-batch2',
        'dir_selector':'11*',
        'sort_method':'name_highfirst',

        # You can also use offset to start the count down the list. For example,
        # this search would capture directores 4-6 in the search, because after
        # implementing the offset of 3, they are the next three.
        'sort_count':3,
        'sort_count_offet':3,
    },

    # Sync the 6 highest-counted folders starting with '11' in their own unison instance
    {
        'syncname':'recent-phone-orders',
        'dir_selector':'11*',
        'sort_method':'name_highfirst',
        'sort_count':6,
    },

    # Sync the 3 highest-counted folders starting with "O" in their own unison instance
    {
        'syncname':'recent-phone-orders',
        'dir_selector':'O*',
        'sort_method':'name_highfirst',
        'sort_count':3,
    },
    # Sync any files not caught above in their own instance
    {
        'dir_selector':'*',
        'overlap':True,
    },

]

# Log file
# log_file = '/opt/unison/config/templates'
# log_file = '/opt/unison/config/templates'

# If set to true, directories will be made if the paths are not found on the system
# If set to false, program will return an error if the directories do not exist
make_root_directories_if_not_found = True
