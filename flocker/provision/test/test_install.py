# Copyright Hybrid Logic Ltd.  See LICENSE file for details.

"""
Tests for ``flocker.provision._install``.
"""

import yaml

from twisted.trial.unittest import SynchronousTestCase

from pyrsistent import freeze, thaw

from .. import PackageSource
from .._install import (
    task_install_flocker,
    task_enable_flocker_agent,
    run, put,
    get_repository_url, UnsupportedDistribution, get_installable_version,
)
from .._ssh import Put
from .._effect import sequence
from ...acceptance.testtools import DatasetBackend

from ... import __version__ as flocker_version


THE_AGENT_YML_PATH = b"/etc/flocker/agent.yml"
BASIC_AGENT_YML = freeze({
    "version": 1,
    "control-service": {
        "hostname": "192.0.2.42",
        "port": 4524,
    },
    "dataset": {
        "backend": "zfs",
    },
})


class EnableFlockerAgentTests(SynchronousTestCase):
    """
    Tests for ``task_enable_flocker_agent``.
    """
    def test_agent_yml(self):
        """
        ```task_enable_flocker_agent`` writes a ``/etc/flocker/agent.yml`` file
        which contains the backend configuration passed to it.
        """
        distribution = u"centos-7"
        control_address = BASIC_AGENT_YML["control-service"]["hostname"]
        expected_pool = u"some-test-pool"
        expected_backend_configuration = dict(pool=expected_pool)
        commands = task_enable_flocker_agent(
            distribution=distribution,
            control_node=control_address,
            dataset_backend=DatasetBackend.lookupByName(
                BASIC_AGENT_YML["dataset"]["backend"]
            ),
            dataset_backend_configuration=expected_backend_configuration,
        )
        [put_agent_yml] = list(
            effect.intent
            for effect in
            commands.intent.effects
            if isinstance(effect.intent, Put)
        )
        # Seems like transform should be usable here but I don't know how.
        expected_agent_config = BASIC_AGENT_YML.set(
            "dataset",
            BASIC_AGENT_YML["dataset"].update(expected_backend_configuration)
        )
        self.assertEqual(
            put(
                content=yaml.safe_dump(thaw(expected_agent_config)),
                path=THE_AGENT_YML_PATH,
            ).intent,
            put_agent_yml,
        )


def _centos7_install_commands(version):
    """
    Construct the command sequence expected for installing Flocker on CentOS 7.

    :param str version: A Flocker native OS package version (a package name
        suffix) like ``"-1.2.3-1"``.

    :return: The sequence of commands expected for installing Flocker on
        CentOS7.
    """
    return sequence([
        run(command="yum clean all"),
        run(command="yum install -y {}".format(get_repository_url(
            distribution='centos-7',
            flocker_version=get_installable_version(flocker_version),
        ))),
        run(command="yum install -y clusterhq-flocker-node" + version)
    ])


class GetRepositoryURL(SynchronousTestCase):
    """
    Tests for ``get_repository_url``.
    """

    def test_fedora_20(self):
        """
        It is possible to get a repository URL for Fedora 20 packages.
        """
        expected = ("https://clusterhq-archive.s3.amazonaws.com/fedora/"
                    "clusterhq-release$(rpm -E %dist).noarch.rpm")

        self.assertEqual(
            get_repository_url(
                distribution='fedora-20',
                flocker_version='0.3.0'),
            expected
        )

    def test_centos_7(self):
        """
        It is possible to get a repository URL for CentOS 7 packages.
        """
        expected = ("https://clusterhq-archive.s3.amazonaws.com/centos/"
                    "clusterhq-release$(rpm -E %dist).noarch.rpm")

        self.assertEqual(
            get_repository_url(
                distribution='centos-7',
                flocker_version='0.3.0'),
            expected
        )

    def test_ubuntu_14_04(self):
        """
        It is possible to get a repository URL for Ubuntu 14.04 packages.
        """
        expected = ("https://clusterhq-archive.s3.amazonaws.com/ubuntu/"
                    "$(lsb_release --release --short)/\\$(ARCH)")

        self.assertEqual(
            get_repository_url(
                distribution='ubuntu-14.04',
                flocker_version='0.3.0'),
            expected
        )

    def test_unsupported_distribution(self):
        """
        An ``UnsupportedDistribution`` error is thrown if a repository for the
        desired distribution cannot be found.
        """
        self.assertRaises(
            UnsupportedDistribution,
            get_repository_url, 'unsupported-os', '0.3.0',
        )

    def test_non_release_ubuntu(self):
        """
        The operating system key for ubuntu has the suffix ``-testing`` for
        non-marketing releases.
        """
        expected = ("https://clusterhq-archive.s3.amazonaws.com/"
                    "ubuntu-testing/"
                    "$(lsb_release --release --short)/\\$(ARCH)")

        self.assertEqual(
            get_repository_url(
                distribution='ubuntu-14.04',
                flocker_version='0.3.0dev1'),
            expected
        )

    def test_non_release_centos(self):
        """
        The operating system key for centos stays the same non-marketing
        releases.
        """
        expected = ("https://clusterhq-archive.s3.amazonaws.com/centos/"
                    "clusterhq-release$(rpm -E %dist).noarch.rpm")

        self.assertEqual(
            get_repository_url(
                distribution='centos-7',
                flocker_version='0.3.0dev1'),
            expected
        )

    def test_non_release_fedora(self):
        """
        The operating system key for fedora stays the same non-marketing
        releases.
        """
        expected = ("https://clusterhq-archive.s3.amazonaws.com/fedora/"
                    "clusterhq-release$(rpm -E %dist).noarch.rpm")

        self.assertEqual(
            get_repository_url(
                distribution='fedora-20',
                flocker_version='0.3.0dev1'),
            expected
        )


class InstallFlockerTests(SynchronousTestCase):
    """
    Tests for ``task_install_flocker``.
    """

    def test_centos_no_arguments(self):
        """
        With no arguments, ``task_install_flocker`` installs the latest
        release.
        """
        distribution = 'centos-7'
        commands = task_install_flocker(distribution=distribution)
        self.assertEqual(commands, _centos7_install_commands(""))

    def test_centos_with_version(self):
        """
        With a ``PackageSource`` containing just a version,
        ``task_install_flocker`` installs that version from our release
        repositories.
        """
        distribution = 'centos-7'
        source = PackageSource(os_version="1.2.3-1")
        commands = task_install_flocker(
            package_source=source,
            distribution=distribution)
        self.assertEqual(commands, _centos7_install_commands("-1.2.3-1"))

    def test_ubuntu_no_arguments(self):
        """
        With no arguments, ``task_install_flocker`` installs the latest
        release.
        """
        distribution = 'ubuntu-14.04'
        commands = task_install_flocker(distribution=distribution)
        self.assertEqual(commands, sequence([
            run(command='apt-get -y install apt-transport-https software-properties-common'),  # noqa
            run(command='add-apt-repository -y ppa:james-page/docker'),
            run(command='add-apt-repository -y "deb {} /"'.format(
                get_repository_url(
                    distribution='ubuntu-14.04',
                    flocker_version=get_installable_version(
                        flocker_version
                    )))),
            run(command='apt-get update'),
            run(command='apt-get -y --force-yes install clusterhq-flocker-node'),  # noqa
        ]))

    def test_ubuntu_with_version(self):
        """
        With a ``PackageSource`` containing just a version,
        ``task_install_flocker`` installs that version from our release
        repositories.
        """
        distribution = 'ubuntu-14.04'
        source = PackageSource(os_version="1.2.3-1")
        commands = task_install_flocker(
            package_source=source,
            distribution=distribution)
        self.assertEqual(commands, sequence([
            run(command='apt-get -y install apt-transport-https software-properties-common'),  # noqa
            run(command='add-apt-repository -y ppa:james-page/docker'),
            run(command='add-apt-repository -y "deb {} /"'.format(
                get_repository_url(
                    distribution='ubuntu-14.04',
                    flocker_version=get_installable_version(
                        flocker_version
                    )))),
            run(command='apt-get update'),
            run(command='apt-get -y --force-yes install clusterhq-flocker-node=1.2.3-1'),  # noqa
        ]))

    def test_ubuntu_with_branch(self):
        """
        With a ``PackageSource`` containing just a branch,
        ``task_install_flocker`` installs that version from buildbot.
        """
        distribution = 'ubuntu-14.04'
        source = PackageSource(branch="branch-FLOC-1234")
        commands = task_install_flocker(
            package_source=source,
            distribution=distribution)
        self.assertEqual(commands, sequence([
            run(command='apt-get -y install apt-transport-https software-properties-common'),  # noqa
            run(command='add-apt-repository -y ppa:james-page/docker'),
            run(command='add-apt-repository -y "deb {} /"'.format(
                get_repository_url(
                    distribution='ubuntu-14.04',
                    flocker_version=get_installable_version(
                        flocker_version
                    )))),
            run(command="add-apt-repository -y "
                        "'deb http://build.clusterhq.com/results/omnibus/branch-FLOC-1234/ubuntu-14.04 /'"),  # noqa
            put(
                content='Package:  *\nPin: origin build.clusterhq.com\nPin-Priority: 900\n',  # noqa
                path='/etc/apt/preferences.d/buildbot-900'),
            run(command='apt-get update'),
            run(command='apt-get -y --force-yes install clusterhq-flocker-node'),  # noqa
        ]))

    def test_with_branch(self):
        """
        With a ``PackageSource`` containing just a branch,
        ``task_install_flocker`` installs the latest build of the branch from
        our build server.
        """
        distribution = 'centos-7'
        source = PackageSource(branch="branch")
        commands = task_install_flocker(
            package_source=source,
            distribution=distribution)
        self.assertEqual(commands, sequence([
            run(command="yum clean all"),
            run(command="yum install -y {}".format(
                get_repository_url(
                    distribution='centos-7',
                    flocker_version=get_installable_version(flocker_version),
                ),
            )),
            put(content="""\
[clusterhq-build]
name=clusterhq-build
baseurl=http://build.clusterhq.com/results/omnibus/branch/centos-7
gpgcheck=0
enabled=0
""",
                path="/etc/yum.repos.d/clusterhq-build.repo"),
            run(command="yum install --enablerepo=clusterhq-build "
                        "-y clusterhq-flocker-node")
        ]))

    def test_with_server(self):
        """
        With a ``PackageSource`` containing a branch and build server,
        ``task_install_flocker`` installs the latest build of the branch from
        that build server.
        """
        distribution = "centos-7"
        source = PackageSource(branch="branch",
                               build_server='http://nowhere.example/')
        commands = task_install_flocker(
            package_source=source,
            distribution=distribution)
        self.assertEqual(commands, sequence([
            run(command="yum clean all"),
            run(command="yum install -y %s" % get_repository_url(
                distribution='centos-7',
                flocker_version=get_installable_version(flocker_version),
            )),
            put(content="""\
[clusterhq-build]
name=clusterhq-build
baseurl=http://nowhere.example/results/omnibus/branch/centos-7
gpgcheck=0
enabled=0
""",
                path="/etc/yum.repos.d/clusterhq-build.repo"),
            run(command="yum install --enablerepo=clusterhq-build "
                        "-y clusterhq-flocker-node")
        ]))

    def test_with_branch_and_version(self):
        """
        With a ``PackageSource`` containing a branch and version,
        ``task_install_flocker`` installs the specifed build of the branch from
        that build server.
        """
        distribution = "centos-7"
        source = PackageSource(branch="branch", os_version='1.2.3-1')
        commands = task_install_flocker(
            package_source=source,
            distribution=distribution)
        self.assertEqual(commands, sequence([
            run(command="yum clean all"),
            run(command="yum install -y %s" % get_repository_url(
                distribution='centos-7',
                flocker_version=get_installable_version(flocker_version),
            )),
            put(content="""\
[clusterhq-build]
name=clusterhq-build
baseurl=http://build.clusterhq.com/results/omnibus/branch/centos-7
gpgcheck=0
enabled=0
""",
                path="/etc/yum.repos.d/clusterhq-build.repo"),
            run(command="yum install --enablerepo=clusterhq-build "
                        "-y clusterhq-flocker-node-1.2.3-1")
        ]))
