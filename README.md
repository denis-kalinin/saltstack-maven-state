You MUST put salt custom modules in the root of repository, because Salt doesn't
consider `gitfs_remotes`'s `root` attribute for custom python modules.
