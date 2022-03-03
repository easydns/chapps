from setuptools import setup
from setuptools.command.install import install
from pathlib import Path
import re
import sys
import atexit
try:
    import dbus
except:
    have_dbus = False
    pass
else:
    have_dbus = True
import logging

### The service should have a role account to run as.  We recommend 'chapps'
SERVICE_ROLEACCOUNT = 'chapps'
### This maps service-script locations in the repo to their descriptive names
SERVICE_DESCRIPTIONS = {
    'services/chapps_outbound_quota.py': 'CHAPPS Outbound Quota Service',
    'services/chapps_outbound_multi.py': 'CHAPPS Outbound Multipolicy Service',
    'services/chapps_greylisting.py': 'CHAPPS Greylisting Service',
}
### create a list of service-script locations for the setup() call
SERVICES = SERVICE_DESCRIPTIONS.keys()

### set logging config; messages at INFO level for now
logger = logging.getLogger( __name__ )
logger.setLevel( logging.INFO )

### Describe a class for doing some post-install work, mainly to set up SystemD service files for venvs
class PostInstallSetup(install):
    """This class can tell if a venv is in use, and format SystemD service startup files appropriately"""
    ### find the base prefix; hopefully pyenv-compatible
    def get_base_prefix_compat( self ):
        return getattr( sys, 'base_prefix', None ) or getattr( sys, 'real_prefix', None ) or sys.prefix
    ### return whether we are in a venv
    def in_virtualenv( self ):
        return self.get_base_prefix_compat() != sys.prefix
    ### build a closure to use with atexit.register()
    def post_install_setup_factory( self ):
        """This function returns a closure suitable for performing the post-install setup"""
        env_settings = {}
        service_descriptions = SERVICE_DESCRIPTIONS
        template_loc = Path( sys.prefix ) / 'chapps' / 'install'
        service_bin = Path( sys.prefix ) / 'bin'
        template_locations = [ template_loc ]
        if self.in_virtualenv():
            python_invocation = str( service_bin / 'python3' )
            ( Path( sys.prefix ) / 'etc' ).mkdir( 511, False, True ) # the mode is really a mask
            env_settings['CHAPPS_CONFIG'] = str( Path( sys.prefix ) / 'etc' / 'chapps.ini' )
        else:
            python_invocation = '/usr/bin/env python3'
            if ( Path( sys.prefix ) / 'local' ).is_dir():
                possible_template_loc = Path( sys.prefix ) / 'local' / 'chapps' / 'install'
                if possible_template_loc.is_dir():
                    template_locations.append( possible_template_loc )
                    service_bin = Path( sys.prefix ) / 'local' / 'bin'
        template_locations.append( Path( sys.prefix ).parent / "install" ) ### the git repo
        ### define a routine for reading in the template; returns template contents followed by location Path object
        def template_reader( template_file ):
            """This function finds and returns the contents of a template"""
            for template_dir in template_locations:
                template_path = template_dir / str( template_file )
                try:
                    with template_path.open() as tfh:
                        template = tfh.read()
                        return template, template_path
                except FileNotFoundError:
                    next
                except Exception:
                    logger.exception( f"reading {template_path}" )
                    next
            return "", None
        ### return the template filled out using the namespace passed in as kwargs
        def fill_template( template, **kwargs ):
            if len( env_settings ) > 0 and 'env_settings_lines' not in kwargs:
                kwargs[ 'env_settings_lines' ] = '\n'.join([ f'Environment="{sym}={val}"' for sym, val in env_settings.items() ])
            else:
                kwargs[ 'env_settings_lines' ] = ''
            return template.format( **kwargs )
        def post_install_setup():
            """This function performs the setup steps: template out service files, then connect them to SystemD"""
            nonlocal python_invocation # this makes sure that the outer definition shows up in locals()
            service_template, template_found = template_reader( 'chapps-systemd-service.tmpl' )
            services_to_enable = []
            if template_found:
                for service_source, service_description in service_descriptions.items():
                    ### set up some variables used by the template
                    service_exec_path = service_bin / Path( service_source ).name
                    service_file_path = template_found.parent / ( Path( service_source ).stem + '.service' )
                    service_roleaccount = SERVICE_ROLEACCOUNT
                    try:
                        with service_file_path.open( 'w' ) as outfile:
                            outfile.write( fill_template( service_template, **locals() ) )
                    except Exception:
                        logger.exception( f"writing {service_file_path}" )
                        next
                    else: # runs if there are no exceptions
                        services_to_enable.append( service_file_path )
                if len( services_to_enable ) > 0:
                    logger.warning(
                        f'The following files were written to {template_found.parent}: ' +
                        ', '.join([ p.name for p in services_to_enable ]) )
                    if have_dbus:
                        sysbus = dbus.SystemBus()
                        systemd = sysbus.get_object( 'org.freedesktop.systemd1', '/org/freedesktop/systemd1' )
                        manager = dbus.Interface( systemd, 'org.freedesktop.systemd1.Manager' )
                        manager.LinkUnitFiles( services_to_enable, False, True )
                        manager.Reload()
                    else:
                        logger.warning( "No dbus client library could be loaded.  Install service files manually.")
                    return
            logger.warning( "No SystemD service file descriptions could be created." )
        return post_install_setup

    def __init__( self, *args, **kwargs ):
        super().__init__( *args, **kwargs )
        self.template_found = [ None ]
        atexit.register( self.post_install_setup_factory() )


VERSIONFILE = 'chapps/_version.py'
verstrline = open(VERSIONFILE, 'rt').read()
VSRE = r"^__version__ = ['\"]([^'\"]*)['\"]"
mo = re.search( VSRE, verstrline, re.M )
if mo:
    verstr = mo.group( 1 )
else:
    raise RuntimeError( f'Unable to find version string in {VERSIONFILE}' )
with open('README.md', 'r') as fh:
    long_description = fh.read()


setup(
    cmdclass={ 'install': PostInstallSetup },
    name = 'chapps',
    packages = ['chapps'],
    data_files = [
        ('chapps', [ 'README.md',
                     'INSTALLATION.md',]),
        ('chapps/install', [
            'install/chapps-systemd-service.tmpl',
        ]),
        ('chapps/postfix/greylisting',    ['postfix/greylisting/main.cf',
                                           'postfix/greylisting/master.cf']),
        ('chapps/postfix/outbound_quota', ['postfix/outbound_quota/main.cf',
                                           'postfix/outbound_quota/master.cf']),
        ('chapps/postfix/null_filter',    ['postfix/null_filter/main.cf',
                                           'postfix/null_filter/master.cf']),
    ],
    scripts = [
        *SERVICES,
        'services/null_filter.py',
        'install/chapps_database_init.py'
    ],
    version = verstr,
    license='MIT',
    description = 'Caching, Highly-Available Postfix Policy Service',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author = 'Caleb S. Cullen',
    author_email = 'ccullen@easydns.com',
    url = 'https://gitlab.int.easydns.net/ccullen/chapps',
    download_url = f'https://github.com/easydns/chapps/tree/main/dist/chapps-{verstr}.tar.gz',
    keywords = ['Postfix', 'Policy', 'Daemon'],
)
