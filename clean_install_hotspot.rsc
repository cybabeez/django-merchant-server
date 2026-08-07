# =====================================================================
# BLANK-SLATE PRODUCTION ROUTEROS 7 CONFIGURATION SCRIPT
# Setup for a reset router with no prior configuration.
# 
# Topology & Addressing:
#   ether1          : WAN (DHCP Client from ISP)
#   ether2 - ether10: Member ports of bridge-main (192.168.88.1/24)
#   ether2          : Server Port (RADIUSdesk / Django / MariaDB at 10.10.10.100)
#   ether3          : Trunk Port to Access Point (VLAN 10 & VLAN 20 Tagged)
#   
# Subnets:
#   bridge-main     : 192.168.88.0/24 (Bridge Gateway: 192.168.88.1)
#   vlan10-mgmt     : 10.10.10.0/24    (Mgmt Gateway: 10.10.10.1)
#   vlan20-hotspot  : 10.20.20.0/24    (Hotspot Gateway: 10.20.20.1)
# =====================================================================

# ---------------------------------------------------------------------
# 1. CREATE BRIDGE AND ADD PORTS
# ---------------------------------------------------------------------
/interface bridge
add name=bridge-main vlan-filtering=no comment="Main L2 Bridge"

/interface bridge port
add bridge=bridge-main interface=ether2 comment="Server Port - Access / Mgmt"
add bridge=bridge-main interface=ether3 pvid=1 comment="Trunk Port to Access Point"
add bridge=bridge-main interface=ether4 comment="Management / LAN Port"
add bridge=bridge-main interface=ether5 comment="Management / LAN Port"
add bridge=bridge-main interface=ether6 comment="LAN Port"
add bridge=bridge-main interface=ether7 comment="LAN Port"
add bridge=bridge-main interface=ether8 comment="LAN Port"
add bridge=bridge-main interface=ether9 comment="LAN Port"
add bridge=bridge-main interface=ether10 comment="LAN Port"

# ---------------------------------------------------------------------
# 2. CREATE VLAN INTERFACES AND BRIDGE VLAN TABLE
# ---------------------------------------------------------------------
/interface vlan
add name=vlan10-mgmt vlan-id=10 interface=bridge-main comment="Management VLAN 10"
add name=vlan20-hotspot vlan-id=20 interface=bridge-main comment="Public Hotspot VLAN 20"

/interface bridge vlan
add bridge=bridge-main vlan-ids=10 tagged=bridge-main,ether3 comment="VLAN 10 Tagged on AP Trunk"
add bridge=bridge-main vlan-ids=20 tagged=bridge-main,ether3 comment="VLAN 20 Tagged on AP Trunk"

# Enable hardware VLAN filtering on the bridge
/interface bridge set bridge-main vlan-filtering=yes

# ---------------------------------------------------------------------
# 3. IP ADDRESS ASSIGNMENTS
# ---------------------------------------------------------------------
/ip address
add address=192.168.88.1/24 interface=bridge-main comment="Bridge 88 Gateway"
add address=10.10.10.1/24 interface=vlan10-mgmt comment="Management VLAN 10 Gateway"
add address=10.20.20.1/24 interface=vlan20-hotspot comment="Hotspot VLAN 20 Gateway"

# ---------------------------------------------------------------------
# 4. IP POOLS & DHCP SERVERS
# ---------------------------------------------------------------------
/ip pool
add name=pool_bridge88 ranges=192.168.88.10-192.168.88.254 comment="Bridge 88 Pool"
add name=pool_vlan10 ranges=10.10.10.150-10.10.10.200 comment="Mgmt VLAN 10 Pool"
add name=pool_vlan20 ranges=10.20.20.10-10.20.20.254 comment="Hotspot VLAN 20 Pool"

/ip dhcp-server
add name=dhcp_bridge88 interface=bridge-main lease-time=12h address-pool=pool_bridge88 disabled=no
add name=dhcp_vlan10 interface=vlan10-mgmt lease-time=12h address-pool=pool_vlan10 disabled=no
add name=dhcp_vlan20 interface=vlan20-hotspot lease-time=1h address-pool=pool_vlan20 disabled=no

/ip dhcp-server network
add address=192.168.88.0/24 gateway=192.168.88.1 dns-server=192.168.88.1,8.8.8.8
add address=10.10.10.0/24 gateway=10.10.10.1 dns-server=10.10.10.1,8.8.8.8
add address=10.20.20.0/24 gateway=10.20.20.1 dns-server=10.20.20.1,8.8.8.8

# ---------------------------------------------------------------------
# 5. WAN INTERNET ACCESS (ether1) & NAT
# ---------------------------------------------------------------------
/ip dhcp-client
add interface=ether1 use-peer-dns=yes use-peer-ntp=yes add-default-route=yes disabled=no comment="WAN Internet DHCP Client"

/ip firewall nat
add chain=srcnat out-interface=ether1 action=masquerade comment="WAN Masquerade"

/ip dns
set allow-remote-requests=yes servers=8.8.8.8,1.1.1.1

# ---------------------------------------------------------------------
# 6. RADIUS INTEGRATION & HOTSPOT SETUP
# ---------------------------------------------------------------------
/radius
add service=hotspot address=10.10.10.100 secret="9373" timeout=3000ms authentication-port=1812 accounting-port=1813 comment="RADIUSdesk Server"

/radius incoming
set accept=yes port=3799

/ip hotspot profile
add name=rd_hsprof hotspot-address=10.20.20.1 dns-name="login.hotspot.local" html-directory=hotspot use-radius=yes login-by=http-pap comment="RADIUSdesk Hotspot Profile"

/ip hotspot
add name=hs_vlan20 interface=vlan20-hotspot address-pool=pool_vlan20 profile=rd_hsprof disabled=no comment="Hotspot Server on VLAN 20"

# ---------------------------------------------------------------------
# 7. FIREWALL FILTER RULES & NETWORK ISOLATION
# ---------------------------------------------------------------------
/ip firewall filter
# --- INPUT CHAIN (Traffic to Router itself) ---
add chain=input connection-state=established,related action=accept comment="Accept Established/Related Connections"
add chain=input connection-state=invalid action=drop comment="Drop Invalid Connections"

add chain=input protocol=udp dst-port=53 action=accept comment="Allow DNS UDP"
add chain=input protocol=tcp dst-port=53 action=accept comment="Allow DNS TCP"
add chain=input protocol=udp dst-port=67-68 action=accept comment="Allow DHCP Requests"
add chain=input protocol=udp dst-port=3799 src-address=10.10.10.100 action=accept comment="Allow RADIUS CoA Port"

# Router Admin Access: Allowed ONLY from bridge-main (192.168.88.0/24) and Mgmt VLAN 10 (10.10.10.0/24)
add chain=input in-interface=bridge-main action=accept comment="Allow Admin Access from 192.168.88.0/24"
add chain=input in-interface=vlan10-mgmt action=accept comment="Allow Admin Access from Mgmt VLAN 10"

# DROP Hotspot VLAN 20 from reaching router administration interfaces
add chain=input in-interface=vlan20-hotspot action=drop comment="BLOCK: Hotspot VLAN 20 direct router access"

# --- FORWARD CHAIN (Inter-VLAN & Internet Traffic) ---
add chain=forward connection-state=established,related action=accept comment="Accept Established/Related Forwarding"
add chain=forward connection-state=invalid action=drop comment="Drop Invalid Forwarding"

# ALLOW Management VLAN 10 to communicate bidirectionally with bridge-main (192.168.88.0/24)
add chain=forward in-interface=vlan10-mgmt out-interface=bridge-main action=accept comment="ALLOW: Mgmt VLAN 10 -> 192.168.88.0/24"
add chain=forward in-interface=bridge-main out-interface=vlan10-mgmt action=accept comment="ALLOW: 192.168.88.0/24 -> Mgmt VLAN 10"

# STRICT ISOLATION: BLOCK Hotspot VLAN 20 from accessing 192.168.88.0/24
add chain=forward in-interface=vlan20-hotspot out-interface=bridge-main action=drop comment="ISOLATION: Block Hotspot VLAN 20 -> 192.168.88.0/24"
add chain=forward in-interface=bridge-main out-interface=vlan20-hotspot action=drop comment="ISOLATION: Block 192.168.88.0/24 -> Hotspot VLAN 20"

# ALLOW WAN (Internet) access for Management and Bridge subnets
add chain=forward in-interface=vlan10-mgmt out-interface=ether1 action=accept comment="Allow Mgmt VLAN 10 -> Internet"
add chain=forward in-interface=bridge-main out-interface=ether1 action=accept comment="Allow Bridge 88 -> Internet"

# ALLOW Hotspot VLAN 20 out to WAN (Internet only)
add chain=forward in-interface=vlan20-hotspot out-interface=ether1 action=accept comment="Allow Hotspot VLAN 20 -> Internet"

# Drop all remaining unauthorized cross-subnet routing
add chain=forward action=drop comment="Drop Unauthorized Forwarding"

# ---------------------------------------------------------------------
# 8. SYSTEM SERVICES & AUTOMATED BACKUP SCHEDULE
# ---------------------------------------------------------------------
/system service
set telnet disabled=yes
set ftp disabled=yes
set www disabled=yes
set api disabled=yes
set api-ssl disabled=yes

/system scheduler
add name="ScheduleNightlyBackup" start-time=03:00:00 interval=1d on-event="/system backup save name=clean_auto_backup; /export file=clean_auto_export" comment="Daily Backup at 3 AM"

:log info "Full blank-slate configuration successfully initialized!"