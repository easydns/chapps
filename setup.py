from setuptools import setup
from setuptools.command.install import install
from pathlib import Path
import jinja2
import re
import sys
import atexit
import dbus

SERVICES = [
    'services/chapps_outbound_quota.py',
    'services/chapps_outbound_multi.py',
    'services/chapps_greylisting.py',
]

SERVICE_DESCRIPTIONS = {
    'services/chapps_outbound_quota.py': 'CHAPPS Outbound Quota Service',
    'services/chapps_outbound_multi.py': 'CHAPPS Outbound Multipolicy Service',
    'services/chapps_greylisting.py': 'CHAPPS Greylisting Service',
}

class PostInstallSetup(install):
    def get_base_prefix_compat( self ):
        return getattr( sys, 'base_prefix', None ) or getattr( sys, 'real_prefix', None ) or sys.prefix

    def in_virtualenv( self ):
        return get_base_prefix_compat() != sys.prefix

    def post_install_setup_factory( self ):
        """This function returns a closure suitable for performing the post-install setup"""
        env_settings = {}
        template_locations = []
        template_found = []
        service_descriptions = SERVICE_DESCRIPTIONS
        if self.in_virtualenv():
            template_loc = Path( sys.prefix ) / "chapps" / "install"
            template_locations.append( template_loc ) if template_loc.is_dir()
            service_bin = Path( sys.prefix ) / "bin"
            python_invocation = str( service_bin / 'python3' )
            env_settings['CHAPPS_CONFIG'] = str( Path( sys.prefix ) / "etc" )
        else:
            template_loc = Path( sys.prefix ) / "chapps" / "install"
            service_bin = Path( sys.prefix )  / "bin"
            if ( Path( sys.prefix ) / "local" ).is_dir():
                possible_template_loc = Path( sys.prefix ) / "local" / "chapps" / "install"
                if possible_template_loc.is_dir():
                    template_loc = possible_template_loc
                    template_locations.append( template_loc )
                    service_bin = Path( sys.prefix ) / "local" / "bin"
            template_locations.append( Path( sys.prefix ) / "chapps" / "install" )
            python_invocation = '/usr/bin/env python3' )
        def template_reader( template_file ):
            """This function finds and returns the contents of a template"""
            for template_dir in template_locations:
                template_path = template_dir / str( template_file )
                try:
                    with template_path.open() as tfh:
                        template_found[0] = template_path
                        return tfh.read_text()
                except FileNotFoundError:
                    next
            return ""
        def post_install_setup():
            """This function performs the setup steps: template out service files, then connect them to SystemD"""
            templater = jinja2.Environment(
                loader=jinja2.FunctionLoader( template_reader ),
                autoescape=jinja2.select_autoescape()
            )
            service_template = templater.get_template( 'chapps-systemd-service.tmpl' )
            services_to_enable = []
            for service_source, service_desc in service_descriptions.items():
                service_exec_path = service_bin / Path( service_source ).name
                service_file_path = template_found[0].parent / ( Path( service.source ).stem + '.service' )
                with service_file_path.open( 'w' ) as outfile:
                    outfile.write( service_template.render( **locals ) )
                services_to_enable.append( service_file_path )
            sysbus = dbus.SystemBus()
            systemd = sysbus.get_object( 'org.freedesktop.systemd1', '/org/freedesktop/systemd1' )
            manager = dbus.Interface( systemd, 'org.freedesktop.systemd1.Manager' )
            manager.LinkUnitFiles( services_to_enable, False, True )
            manager.Reload()
        return post_install_setup

    def __init__( self, *args, **kwargs ):
        super().__init__( *args, **kwargs )
        atexit.register( self.post_install_setup_factory() )



VERSIONFILE = 'chapps/_version.py'
verstrline = open(VERSIONFILE, 'rt').read()
VSRE = r"^__version__ = ['\"]([^'\"]*)['\"]"
mo = re.search( VSRE, verstrline, re.M )
if mo:
    verstr = mo.group( 1 )
else:
    raise RuntimeError( f"Unable to find version string in {VERSIONFILE}" )
with open("README.md", "r") as fh:
    long_description = fh.read()


setup(
  cmdclass={ 'install': PostInstallSetup }
  name = 'chapps',
  packages = ['chapps'],
  package_data = { 'chapps' : }
  data_files = [
      ('chapps', [ 'README.md',
             'INSTALLATION.md',]),
      ('chapps/install', [ 'install/chapps_greylisting.service',
                    'install/chapps_oqp.service',
                    'install/chapps_multi.service',
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
  long_description_content_type="text/markdown",
  author = 'Caleb S. Cullen',
  author_email = 'ccullen@easydns.com',
  url = 'https://gitlab.int.easydns.net/ccullen/chapps',
  download_url = f'https://github.com/easydns/chapps/tree/main/dist/chapps-{verstr}.tar.gz',
  keywords = ['Postfix', 'Policy', 'Daemon'],
  # install_requires=[       # dependencies come from setup.cfg now
  #         'redis',
  #         'expiring-dict',
  #         'dnspython',
  #         'mariadb',
  #         'pyspf',
  #         'python-pidfile',
  #     ],
)
