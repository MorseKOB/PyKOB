from distutils.core import setup

setup(name = 'PyKOB',
      version = '1.1.4',
      description = 'MorseKOB library package',
      author = 'Les Kerr',
      author_email = 'les@morsekob.org',
      url = 'http://sites.google.com/site/morsekob',
      packages = ['pykob'],
      package_data = {'pykob': ['*.wav', '*.txt']}
     )
