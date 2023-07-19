import gevent
import gevent.monkey
gevent.monkey.patch_socket()
gevent.monkey.patch_select()
gevent.monkey.patch_ssl()


import logging

from contextlib import contextmanager
from steam.exceptions import SteamError
from steam.enums import EResult
from steamctl.clients import CachingSteamClient

LOG = logging.getLogger(__name__)

APP = 730
DEPOT = 731
MANIFEST = 9115840458958238518

@contextmanager
def init_clients(args):
    s = CachingSteamClient()

    if args.cell_id is not None:
        s.cell_id = args.cell_id

    cdn = s.get_cdnclient()

    # for everything else we need SteamClient and CDNClient

    # only login when we may need it

    result = s.login_from_args(args)

    if result == EResult.OK:
        LOG.info("Login to Steam successful")
    else:
        raise SteamError("Failed to login: %r" % result)

    cached_manifest = cdn.get_cached_manifest(args.app, args.depot, args.manifest)

    decrypt = True

    # load the manifest
    try:
        if not cached_manifest:
            manifest_code = cdn.get_manifest_request_code(
                APP, DEPOT, 9115840458958238518
            )
        else:
            manifest_code = None

        manifests = [
            cdn.get_manifest(
                APP, DEPOT, 9115840458958238518,
                decrypt=decrypt, manifest_request_code=manifest_code
            )
        ]
    except SteamError as exp:
        if exp.eresult == EResult.AccessDenied:
            raise SteamError("This account doesn't have access to the app depot", exp.eresult)
        elif 'HTTP Error 404' in str(exp):
            raise SteamError("Manifest not found on CDN")
        else:
            raise

    LOG.debug("Got manifests: %r", manifests)

    yield s, cdn, manifests

    # clean and exit
    cdn.save_cache()
    s.disconnect()

def cmd_depot_manifestdl(args):
    try:
        with init_clients(args) as (_, cdn, manifests):
            print("I don't know what i'm doing")

    except SteamError as exp:
        LOG.error(str(exp))
        return 1  # error