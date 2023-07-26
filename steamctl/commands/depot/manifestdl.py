import gevent
import gevent.monkey
gevent.monkey.patch_socket()
gevent.monkey.patch_select()
gevent.monkey.patch_ssl()


import logging

from contextlib import contextmanager
from steam.exceptions import SteamError
from steam.enums import EResult
from steam.client import EMsg
from steamctl.clients import CachingSteamClient
from steamctl.utils.format import fmt_datetime

LOG = logging.getLogger(__name__)

APP = 730
DEPOT_TEST = 731
MANIFEST = {731:[9115840458958238518, 4416248450556854960], 732:[3227301410759530897]}

MANIFESTS = {2347770:[1077985928720806923 ], 2347771:[8327826369021188923], 2347779: [6930564943378593358]}

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

    decrypt = True

    manifests = []

    mani = 0
    depot = 0

    LOG.info("Checking licenses")

    if s.logged_on and not s.licenses and s.steam_id.type != s.steam_id.EType.AnonUser:
        s.wait_event(EMsg.ClientLicenseList, raises=False, timeout=10)

    cdn.load_licenses()

    if APP not in cdn.licensed_app_ids:
        raise SteamError("No license available for App ID: %s" % APP, EResult.AccessDenied)


    LOG.info("Checking change list")
    s.check_for_changes()

    # load the manifest
    try:
        args.app = APP
        for depot in ['2347770', '2347771', '2347779']:
            dict_args = vars(args)
            if dict_args.get(depot):
                args.depot = int(depot)
                for mani in dict_args.get(depot).split():
                    args.manifest = int(mani)
                    LOG.info(f"Getting manifest {args.manifest} for depot {args.depot} for app {args.app}")
                    cached_manifest = cdn.get_cached_manifest(APP, args.depot, args.manifest)
                    if not cached_manifest:
                        manifest_code = cdn.get_manifest_request_code(APP, args.depot, args.manifest)
                        manifests.append(cdn.get_manifest(APP, args.depot, args.manifest, decrypt=decrypt, manifest_request_code=manifest_code))
                    else:
                        manifests.append(cached_manifest)
                
    except SteamError as exp:
        if exp.eresult == EResult.AccessDenied:
            LOG.warn(f"This account doesn't have access to the app depot {depot} {exp.eresult}")
        elif 'HTTP Error 404' in str(exp):
            LOG.warn(f"Manifest {mani} not found on CDN")
        else:
            raise

    LOG.info("Got manifests: %r", manifests)

    yield s, cdn, manifests

    # clean and exit
    cdn.save_cache()
    s.disconnect()

def cmd_depot_manifestdl(args):
    try:
        with init_clients(args) as (_, cdn, manifests):
            print("I don't know what i'm doing")
            for i, manifest in enumerate(manifests, 1):
                print("Manifest GID:", manifest.metadata.gid_manifest)
                print("Created On:", fmt_datetime(manifest.metadata.creation_time))


                if cdn:
                    depot_info = cdn.app_depots.get(manifest.app_id, {}).get(str(manifest.metadata.depot_id))

                    if depot_info:
                        print("Config:", depot_info.get('config', '{}'))
                        if 'dlcappid' in depot_info:
                            print("DLC AppID:", depot_info['dlcappid'])

                        print("Branch:", args.branch)
                        print("Open branches:", ', '.join(depot_info.get('manifests', {}).keys()))
                        print("Protected branches:", ', '.join(depot_info.get('encryptedmanifests', {}).keys()))

                if i != len(manifests):
                    print("-"*40)


    except SteamError as exp:
        LOG.error(str(exp))
        return 1  # error