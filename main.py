from configparser import SafeConfigParser
import meraki
from tabulate import tabulate
import pandas as pd

parser = SafeConfigParser()
parser.read("config.ini")

radiusServers = []
radiusAccountingServers = []
ssids = []

def print_tabulate(data):
    print(tabulate(pd.DataFrame(data), headers='keys', tablefmt='fancy_grid'))

for section_name in parser.sections():
    if 'radius_auth_' in section_name:
        radius_servers = {
            'name': section_name,
            'host': parser.get(section_name, 'host'),
            'secret': parser.get(section_name, 'secret'),
            'port': parser.get(section_name, 'port')
        }
        radiusServers.append(radius_servers)
    if 'radius_acct_' in section_name:
        radius_acct_servers = {
            'name': section_name,
            'host': parser.get(section_name, 'host'),
            'secret': parser.get(section_name, 'secret'),
            'port': parser.get(section_name, 'port')
        }
        radiusAccountingServers.append(radius_acct_servers)
    if 'ssid_' in section_name:
        if parser.get(section_name, 'auth_enabled') != "True" and parser.get(section_name, 'auth_preference') != "None":
            print("If auth_enabled is set to False, auth_preference must be set to None.")
            exit()
        elif parser.get(section_name, 'auth_preference') == 'None':
            print("If auth_enabled is set to True, auth_preference cannot be set to None.")
            exit()
        elif parser.get(section_name, 'auth_enabled') != "True" and parser.get(section_name, "acct_enabled") == "True":
            print("If auth_enabled is not set to True, acct_enabled cannot be set to True.")
            exit()
        elif parser.get(section_name, 'acct_enabled') == "True" and parser.get(section_name, "acct_preference") == "None":
            print("If acct_enabled is set to True, acct_preference must not be set to None.")
            exit()
        ssid = {
            "name": section_name,
            "auth_enabled": parser.get(section_name, 'auth_enabled'),
            "auth_preference": parser.get(section_name, 'auth_preference').split(", "),
            "acct_enabled": parser.get(section_name, 'acct_enabled'),
            "acct_preference": parser.get(section_name, 'acct_preference').split(", ")
        }
        ssids.append(ssid)

print_tabulate(radiusServers)
print_tabulate(radiusAccountingServers)
print_tabulate(ssids)


dashboard = meraki.DashboardAPI(api_key=parser.get('credentials','api_key'), log_path='./logs')

networks = dashboard.organizations.getOrganizationNetworks(organizationId=parser.get('credentials', 'org_id'))

net_ids = [net['id'] for net in networks if net['name']==parser.get('target_networks', 'network_name')]

for net_id in net_ids:
    net_ssids = dashboard.wireless.getNetworkWirelessSsids(net_id)
    for net_ssid in net_ssids:
        proceed = ""
        if net_ssid['name'] in [ssid['name'] for ssid in ssids]:
            print(net_ssid)
            if net_ssid['authMode'] != '8021x-radius':
                proceed = input(f"In network {net_id}, SSID {net_ssid['name']} is not configured for 802.1X+RADIUS authentication. Do you want to set this SSID to use 802.1X+RADIUS? (Y/N): ")
                if proceed == 'Y':
                    print(f"Updating SSID {net_ssid['name']} to 802.1X+RADIUS.")
                    net_ssid['authMode'] = '8021x-radius'
                    net_ssid['encryptionMode'] = 'wpa'
                    net_ssid['wpaEncryptionMode'] = 'WPA2 only'
                elif proceed == 'N':
                    print(f"Skipping SSID {net_ssid['name']}")
                    continue
                else:
                    print(f"Invalid input. Skipping SSID {net_ssid['name']}")
                    continue
            elif net_ssid['authMode']=='8021x-radius':
                if 'radiusServers' in net_ssid.keys():
                    print(f"In network {net_id}, SSID {net_ssid['name']} has the following RADIUS servers configured:")
                    print_tabulate(net_ssid['radiusServers'])
                if 'radiusAccountingServers' in net_ssid.keys():
                    print(f"and the following RADIUS accounting servers configured:")
                    print_tabulate(net_ssid['radiusAccountingServers'])
            for conf_ssid in ssids:
                if conf_ssid['name']==net_ssid['name']:
                    print(f"Do you wish to set SSID {net_ssid['name']} in network {net_id} with the following RADIUS settings?")
                    sorted_rs = []
                    if conf_ssid['auth_enabled']=="True":
                        for crs in conf_ssid['auth_preference']:
                            for rs in radiusServers:
                                if crs == rs['name']:
                                    upd_rs = {k: rs[k] for k in rs.keys() - {"name"}}
                                    sorted_rs.append(upd_rs)
                        print("RADIUS Servers:")
                        print_tabulate(sorted_rs)
                    sorted_ras = []
                    if conf_ssid['acct_enabled']=="True":
                        for cras in conf_ssid['acct_preference']:
                            for ras in radiusAccountingServers:
                                if cras == ras['name']:
                                    upd_ras = {k: ras[k] for k in ras.keys() - {"name"}}
                                    sorted_ras.append(upd_ras)
                        print("RADIUS Accounting Servers:")
                        print_tabulate(sorted_ras)
                    proceed = input("Confirm?: (Y/N)")
                    if proceed == 'Y':
                        if conf_ssid['auth_enabled']:
                            net_ssid['radiusServers']=sorted_rs
                        if conf_ssid['acct_enabled']:
                            net_ssid['radiusAccountingServers']=sorted_ras
                        upd_ssid = {k: net_ssid[k] for k in net_ssid.keys() - {"number", "radiusFailoverPolicy", "radiusLoadBalancingPolicy"}}
                        upd_ssid['encryptionMode'] = 'wpa'
                        print(net_ssid)
                        print(upd_ssid)
                        dashboard.wireless.updateNetworkWirelessSsid(
                            networkId=net_id,
                            number=net_ssid["number"],
                            **upd_ssid
                        )
                    elif proceed == 'N':
                        print(f"User skipped provisioning SSID {net_ssid['name']} for network {net_id}.")
                        continue
                    else:
                        print(f"Invalid input, only Y or N are accepted. Skipping this SSID.")
                        continue




