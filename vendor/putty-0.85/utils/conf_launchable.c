/*
 * Determine whether or not a Conf represents a session which can
 * sensibly be launched right now.
 */

#include "putty.h"

bool conf_launchable(Conf *conf)
{
    /* Local terminals have no network destination to validate. */
    if (!backends[0])
        return true;
    if (conf_get_int(conf, CONF_protocol) == PROT_SERIAL)
        return conf_get_str(conf, CONF_serline)[0] != 0;
    else
        return conf_get_str(conf, CONF_host)[0] != 0;
}
