# Copyright Hybrid Logic Ltd.  See LICENSE file for details.

"""
Tests for moving applications between nodes.
"""
from twisted.trial.unittest import TestCase

from .testtools import (require_cluster,
                        MONGO_APPLICATION, MONGO_IMAGE,
                        get_mongo_application, require_flocker_cli)


class MovingApplicationTests(TestCase):
    """
    Tests for moving applications between nodes.

    Similar to http://doc-dev.clusterhq.com/gettingstarted/tutorial/
    moving-applications.html#moving-an-application
    """
    @require_flocker_cli
    @require_cluster(2)
    def test_moving_application(self, cluster):
        """
        After deploying an application to one node and then moving it onto
        another node, it is only on the second node. This only tests that the
        application is present with the given name and image on a second node
        after it has been moved from the first.
        """
        node_1, node_2 = cluster.nodes

        minimal_deployment = {
            u"version": 1,
            u"nodes": {
                node_1.address: [MONGO_APPLICATION],
                node_2.address: [],
            },
        }

        minimal_application = {
            u"version": 1,
            u"applications": {
                MONGO_APPLICATION: {
                    u"image": MONGO_IMAGE,
                },
            },
        }

        cluster.flocker_deploy(self, minimal_deployment, minimal_application)

        minimal_deployment_moved = {
            u"version": 1,
            u"nodes": {
                node_1.address: [],
                node_2.address: [MONGO_APPLICATION],
            },
        }

        cluster.flocker_deploy(
            self, minimal_deployment_moved, minimal_application)

        return cluster.assert_expected_deployment(self, {
            node_1.address: set([]),
            node_2.address: set([get_mongo_application()])
        })
