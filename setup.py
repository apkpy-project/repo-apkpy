from setuptools import setup, find_namespace_packages

setup(
    name='apkpy',
    version='1.13.0',
    author='Martim',
    # Apache 2.0, with an exception at the end of LICENSE for what ApkPy
    # writes into the apps it builds.
    license='Apache-2.0',
    license_files=['LICENSE', 'NOTICE', 'AUTHORS'],
    description='Build native Android apps in pure Python with a fast desktop preview and native Java/XML output.',
    # PYPI.md is the page PyPI shows; README.md is the shorter one GitHub
    # shows.
    long_description=open('PYPI.md', encoding='utf-8').read(),
    long_description_content_type='text/markdown',
    # PyPI shows this as "Homepage": the site, so the package page leads to it.
    url='https://repo-apkpy.pages.dev/',
    # apkpy_lib and nothing else. click is a dependency (below) and colorama
    # is click's own on Windows: copies of both used to be packed into the
    # wheel as well, so installing ApkPy wrote over whatever click the
    # person already had, and uninstalling it took click's files away.
    packages=find_namespace_packages(
        include=['apkpy_lib*'],
    ),
    include_package_data=True,
    # AES-GCM for crypto.encrypt(..., password=...) in the desktop
    # Previewer only. The built Android app needs nothing extra, so
    # this is not worth a compiled dependency for everyone.
    extras_require={'crypto': ['cryptography>=41']},
    install_requires=[
        'click',
        # Installed by default so video() works in the desktop Previewer
        # immediately after ``pip install apkpy``.
        'opencv-python-headless>=4.8',
        'Pillow>=9.0',
        'sounddevice>=0.4.6',
        'imageio-ffmpeg>=0.6.0; python_version >= "3.9"',
        'imageio-ffmpeg==0.5.1; python_version < "3.9"',
        # apkpy.toml is read with tomllib, which is Python 3.11 and later.
        # Before it, without this, the file was skipped with a warning and
        # the app was built under the default name and application id.
        'tomli>=2.0.1; python_version < "3.11"',
    ],
    entry_points={
        'console_scripts': [
            'apkpy=apkpy_lib.cli:main',
        ],
    },
    keywords=[
        'android', 'apk', 'python', 'mobile', 'app', 'framework',
        'android-development', 'no-java', 'python-to-android',
        'native-android', 'mobile-development', 'gui', 'sqlite',
        'http', 'rest-api', 'hot-reload', 'compiler', 'build-tool',
        'workmanager', 'background-jobs', 'offline-queue', 'background-tasks',
        'file-picker', 'file-upload', 'document-picker',
        'storage-access-framework',
    ],
    classifiers=[
        # Development status
        "Development Status :: 4 - Beta",
        # Audience
        "Intended Audience :: Developers",
        "Intended Audience :: Education",
        # Topic
        "Topic :: Software Development :: Libraries :: Application Frameworks",
        "Topic :: Software Development :: Compilers",
        "Topic :: Software Development :: Build Tools",
        "Topic :: Multimedia :: Graphics",
        # Language
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        # OS
        "Operating System :: OS Independent",
        # Environment
        "Environment :: Console",
    ],
    project_urls={
        'Documentation': 'https://repo-apkpy.pages.dev/getting-started/',
        'Source': 'https://github.com/apkpy-project/repo-apkpy',
        'Changelog': 'https://github.com/apkpy-project/repo-apkpy/blob/main/CHANGELOG.md',
        'Bug Tracker': 'https://github.com/apkpy-project/repo-apkpy/issues',
    },
    python_requires='>=3.8',
)
