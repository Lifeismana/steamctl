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
from steamctl.utils.format import fmt_datetime

LOG = logging.getLogger(__name__)

APP = 730
DEPOT = 731
MANIFEST = {731:[9115840458958238518, 4416248450556854960], 732:[3227301410759530897]}

MANIFESTS = {2347770: [ 4473487723012660428, 992161785091620447, 7408154579934899661, 5524296447051579998, 7780284852338481782, 1817955853493084055, 6753534390520317003, 5946644637254121542, 2127588128906927923, 4543955829510800454, 1035466373246425013, 2151952796073781340, 5357854883766668831, 2182233850230741503, 281936315406757955, 420087000680427403, 8272899024788234712, 3864476401627506266, 9012759399567640305, 7490738140762486640, 3744870746062564069, 862063560468773960], 
             2347771: [3805708056119697931, 8254570254769889147, 4408975132623504081, 148084638517423330, 241575148638211373, 5450149741582443877, 4646106614081054076, 441916249227414378, 7319276772564135830, 3754018638600474871, 3726477318459807170, 694099313588605089, 4646777846649292218, 8227697818958662323, 18041795805829013, 8952376812951361193, 7526142366326028958, 2519456234678493914, 5271715121203446825, 932998659899485441, 2687474053035626042, 9211829238844378553],
2347779: [187047130493366144, 4022071540859827277, 1690370660893930362, 1725127524740368673, 7321994633680785468, 5179751417437217568, 2286149188409598450, 6648241233197971950, 9088407507291724591, 1774080703881064639, 186663600593146917, 7027319872198561758, 7996723125568704577, 209895134542222148, 3836757039368092987, 1923413707392182986, 6684364688997334667, 2600984163371577443, 7985311292641617795, 6866326769762295434, 577283016894644358, 5736705030505559513]
}

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

    # load the manifest
    try:
        for depot in MANIFESTS:
            for mani in MANIFESTS[depot]:
                cached_manifest = cdn.get_cached_manifest(APP, depot, mani)
                if not cached_manifest:
                    manifest_code = cdn.get_manifest_request_code(
                        APP, depot, mani
                    )
                else:
                    manifest_code = None
                manifests.append(cdn.get_manifest(APP, depot, mani, decrypt=decrypt, manifest_request_code=manifest_code))
    except SteamError as exp:
        if exp.eresult == EResult.AccessDenied:
            raise SteamError("This account doesn't have access to the app depot", exp.eresult)
        elif 'HTTP Error 404' in str(exp):
            LOG.warn(f"Manifest {mani} not found on CDN")
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