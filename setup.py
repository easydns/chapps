from setuptools import setup
import re
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
  name = 'chapps',
  packages = ['chapps'],
  data_files = [
      ('', [ 'README.md',
             'INSTALLATION.md',]),
      ('install', ['install/chapps_greylisting.service',
                   'install/chapps_oqp.service',
                   'install/chapps_multi.service',
                   'install/install.sh']),
      ('postfix/greylisting',    ['postfix/greylisting/main.cf',
                                  'postfix/greylisting/master.cf']),
      ('postfix/outbound_quota', ['postfix/outbound_quota/main.cf',
                                  'postfix/outbound_quota/master.cf']),
      ('postfix/null_filter',    ['postfix/null_filter/main.cf',
                                  'postfix/null_filter/master.cf']),
  ],
  scripts = [
      'services/chapps_outbound_quota.py',
      'services/chapps_outbound_multi.py',
      'services/chapps_greylisting.py',
      'services/null_filter.py',
      'install/chapps_database_init.py'
  ],
  version = verstr,
  python_requires='>=3.8',
  license='MIT',
  description = 'Caching, Highly-Available Postfix Policy Service',
  long_description=long_description,
  long_description_content_type="text/markdown",
  author = 'Caleb S. Cullen',
  author_email = 'ccullen@easydns.com',
  url = 'https://gitlab.int.easydns.net/ccullen/chapps',
  download_url = f'https://github.com/easydns/chapps/tree/main/dist/chapps-{verstr}.tar.gz',
  keywords = ['Postfix', 'Policy', 'Daemon'],
  install_requires=[
          'redis',
          'expiring-dict',
          'dnspython',
          'mariadb',
          'pyspf',
          'python-pidfile',
      ],
  classifiers=[
    'Development Status :: 3 - Alpha',
    'Environment :: No Input/Output (Daemon)',
    'Intended Audience :: System Administrators',
    'Operating System :: POSIX :: Linux',
    'Topic :: Communications :: Email :: Filters',
    'License :: OSI Approved :: MIT License',
    'Programming Language :: Python :: 3.8',
    'Programming Language :: Python :: 3.9',
    'Programming Language :: Python :: 3.10',
  ],
)
