#!/usr/bin/env python

""" nl80211_h.py: 802.11 netlink interface public header

A port of nl80211.h to python
/*
 * 802.11 netlink interface public header
 *
 * Copyright 2006-2010 Johannes Berg <johannes@sipsolutions.net>
 * Copyright 2008 Michael Wu <flamingice@sourmilk.net>
 * Copyright 2008 Luis Carlos Cobo <luisca@cozybit.com>
 * Copyright 2008 Michael Buesch <m@bues.ch>
 * Copyright 2008, 2009 Luis R. Rodriguez <lrodriguez@atheros.com>
 * Copyright 2008 Jouni Malinen <jouni.malinen@atheros.com>
 * Copyright 2008 Colin McCabe <colin@cozybit.com>
 *
 * Permission to use, copy, modify, and/or distribute this software for any
 * purpose with or without fee is hereby granted, provided that the above
 * copyright notice and this permission notice appear in all copies.
 *
 * THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
 * WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
 * MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
 * ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
 * WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
 * ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
 * OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
 *
 */
Most of these constants are not used but are left for possible future use
"""

__name__ = 'nl80211_h'
__license__ = 'GPL v3.0'
__version__ = '0.0.2'
__date__ = 'March 2016'
__author__ = 'Dale Patterson'
__maintainer__ = 'Dale Patterson'
__email__ = 'wraith.wireless@yandex.com'
__status__ = 'Development'

NL80211_GENL_NAME = 'nl80211'

"""
/**
 * enum nl80211_commands - supported nl80211 commands
 *
 * @NL80211_CMD_UNSPEC: unspecified command to catch errors
 *
 * @NL80211_CMD_GET_WIPHY: request information about a wiphy or dump request
 *	to get a list of all present wiphys.
 * @NL80211_CMD_SET_WIPHY: set wiphy parameters, needs %NL80211_ATTR_WIPHY or
 *	%NL80211_ATTR_IFINDEX; can be used to set %NL80211_ATTR_WIPHY_NAME,
 *	%NL80211_ATTR_WIPHY_TXQ_PARAMS, %NL80211_ATTR_WIPHY_FREQ (and the
 *	attributes determining the channel width; this is used for setting
 *	monitor mode channel),  %NL80211_ATTR_WIPHY_RETRY_SHORT,
 *	%NL80211_ATTR_WIPHY_RETRY_LONG, %NL80211_ATTR_WIPHY_FRAG_THRESHOLD,
 *	and/or %NL80211_ATTR_WIPHY_RTS_THRESHOLD.
 *	However, for setting the channel, see %NL80211_CMD_SET_CHANNEL
 *	instead, the support here is for backward compatibility only.
 * @NL80211_CMD_NEW_WIPHY: Newly created wiphy, response to get request
 *	or rename notification. Has attributes %NL80211_ATTR_WIPHY and
 *	%NL80211_ATTR_WIPHY_NAME.
 * @NL80211_CMD_DEL_WIPHY: Wiphy deleted. Has attributes
 *	%NL80211_ATTR_WIPHY and %NL80211_ATTR_WIPHY_NAME.
 *
 * @NL80211_CMD_GET_INTERFACE: Request an interface's configuration;
 *	either a dump request on a %NL80211_ATTR_WIPHY or a specific get
 *	on an %NL80211_ATTR_IFINDEX is supported.
 * @NL80211_CMD_SET_INTERFACE: Set type of a virtual interface, requires
 *	%NL80211_ATTR_IFINDEX and %NL80211_ATTR_IFTYPE.
 * @NL80211_CMD_NEW_INTERFACE: Newly created virtual interface or response
 *	to %NL80211_CMD_GET_INTERFACE. Has %NL80211_ATTR_IFINDEX,
 *	%NL80211_ATTR_WIPHY and %NL80211_ATTR_IFTYPE attributes. Can also
 *	be sent from userspace to request creation of a new virtual interface,
 *	then requires attributes %NL80211_ATTR_WIPHY, %NL80211_ATTR_IFTYPE and
 *	%NL80211_ATTR_IFNAME.
 * @NL80211_CMD_DEL_INTERFACE: Virtual interface was deleted, has attributes
 *	%NL80211_ATTR_IFINDEX and %NL80211_ATTR_WIPHY. Can also be sent from
 *	userspace to request deletion of a virtual interface, then requires
 *	attribute %NL80211_ATTR_IFINDEX.
 *
 * @NL80211_CMD_GET_KEY: Get sequence counter information for a key specified
 *	by %NL80211_ATTR_KEY_IDX and/or %NL80211_ATTR_MAC.
 * @NL80211_CMD_SET_KEY: Set key attributes %NL80211_ATTR_KEY_DEFAULT,
 *	%NL80211_ATTR_KEY_DEFAULT_MGMT, or %NL80211_ATTR_KEY_THRESHOLD.
 * @NL80211_CMD_NEW_KEY: add a key with given %NL80211_ATTR_KEY_DATA,
 *	%NL80211_ATTR_KEY_IDX, %NL80211_ATTR_MAC, %NL80211_ATTR_KEY_CIPHER,
 *	and %NL80211_ATTR_KEY_SEQ attributes.
 * @NL80211_CMD_DEL_KEY: delete a key identified by %NL80211_ATTR_KEY_IDX
 *	or %NL80211_ATTR_MAC.
 *
 * @NL80211_CMD_GET_BEACON: (not used)
 * @NL80211_CMD_SET_BEACON: change the beacon on an access point interface
 *	using the %NL80211_ATTR_BEACON_HEAD and %NL80211_ATTR_BEACON_TAIL
 *	attributes. For drivers that generate the beacon and probe responses
 *	internally, the following attributes must be provided: %NL80211_ATTR_IE,
 *	%NL80211_ATTR_IE_PROBE_RESP and %NL80211_ATTR_IE_ASSOC_RESP.
 * @NL80211_CMD_START_AP: Start AP operation on an AP interface, parameters
 *	are like for %NL80211_CMD_SET_BEACON, and additionally parameters that
 *	do not change are used, these include %NL80211_ATTR_BEACON_INTERVAL,
 *	%NL80211_ATTR_DTIM_PERIOD, %NL80211_ATTR_SSID,
 *	%NL80211_ATTR_HIDDEN_SSID, %NL80211_ATTR_CIPHERS_PAIRWISE,
 *	%NL80211_ATTR_CIPHER_GROUP, %NL80211_ATTR_WPA_VERSIONS,
 *	%NL80211_ATTR_AKM_SUITES, %NL80211_ATTR_PRIVACY,
 *	%NL80211_ATTR_AUTH_TYPE, %NL80211_ATTR_INACTIVITY_TIMEOUT,
 *	%NL80211_ATTR_ACL_POLICY and %NL80211_ATTR_MAC_ADDRS.
 *	The channel to use can be set on the interface or be given using the
 *	%NL80211_ATTR_WIPHY_FREQ and the attributes determining channel width.
 * @NL80211_CMD_NEW_BEACON: old alias for %NL80211_CMD_START_AP
 * @NL80211_CMD_STOP_AP: Stop AP operation on the given interface
 * @NL80211_CMD_DEL_BEACON: old alias for %NL80211_CMD_STOP_AP
 *
 * @NL80211_CMD_GET_STATION: Get station attributes for station identified by
 *	%NL80211_ATTR_MAC on the interface identified by %NL80211_ATTR_IFINDEX.
 * @NL80211_CMD_SET_STATION: Set station attributes for station identified by
 *	%NL80211_ATTR_MAC on the interface identified by %NL80211_ATTR_IFINDEX.
 * @NL80211_CMD_NEW_STATION: Add a station with given attributes to the
 *	the interface identified by %NL80211_ATTR_IFINDEX.
 * @NL80211_CMD_DEL_STATION: Remove a station identified by %NL80211_ATTR_MAC
 *	or, if no MAC address given, all stations, on the interface identified
 *	by %NL80211_ATTR_IFINDEX.
 *
 * @NL80211_CMD_GET_MPATH: Get mesh path attributes for mesh path to
 * 	destination %NL80211_ATTR_MAC on the interface identified by
 * 	%NL80211_ATTR_IFINDEX.
 * @NL80211_CMD_SET_MPATH:  Set mesh path attributes for mesh path to
 * 	destination %NL80211_ATTR_MAC on the interface identified by
 * 	%NL80211_ATTR_IFINDEX.
 * @NL80211_CMD_NEW_MPATH: Create a new mesh path for the destination given by
 *	%NL80211_ATTR_MAC via %NL80211_ATTR_MPATH_NEXT_HOP.
 * @NL80211_CMD_DEL_MPATH: Delete a mesh path to the destination given by
 *	%NL80211_ATTR_MAC.
 * @NL80211_CMD_NEW_PATH: Add a mesh path with given attributes to the
 *	the interface identified by %NL80211_ATTR_IFINDEX.
 * @NL80211_CMD_DEL_PATH: Remove a mesh path identified by %NL80211_ATTR_MAC
 *	or, if no MAC address given, all mesh paths, on the interface identified
 *	by %NL80211_ATTR_IFINDEX.
 * @NL80211_CMD_SET_BSS: Set BSS attributes for BSS identified by
 *	%NL80211_ATTR_IFINDEX.
 *
 * @NL80211_CMD_GET_REG: ask the wireless core to send us its currently set
 * 	regulatory domain.
 * @NL80211_CMD_SET_REG: Set current regulatory domain. CRDA sends this command
 *	after being queried by the kernel. CRDA replies by sending a regulatory
 *	domain structure which consists of %NL80211_ATTR_REG_ALPHA set to our
 *	current alpha2 if it found a match. It also provides
 * 	NL80211_ATTR_REG_RULE_FLAGS, and a set of regulatory rules. Each
 * 	regulatory rule is a nested set of attributes  given by
 * 	%NL80211_ATTR_REG_RULE_FREQ_[START|END] and
 * 	%NL80211_ATTR_FREQ_RANGE_MAX_BW with an attached power rule given by
 * 	%NL80211_ATTR_REG_RULE_POWER_MAX_ANT_GAIN and
 * 	%NL80211_ATTR_REG_RULE_POWER_MAX_EIRP.
 * @NL80211_CMD_REQ_SET_REG: ask the wireless core to set the regulatory domain
 * 	to the specified ISO/IEC 3166-1 alpha2 country code. The core will
 * 	store this as a valid request and then query userspace for it.
 *
 * @NL80211_CMD_GET_MESH_CONFIG: Get mesh networking properties for the
 *	interface identified by %NL80211_ATTR_IFINDEX
 *
 * @NL80211_CMD_SET_MESH_CONFIG: Set mesh networking properties for the
 *      interface identified by %NL80211_ATTR_IFINDEX
 *
 * @NL80211_CMD_SET_MGMT_EXTRA_IE: Set extra IEs for management frames. The
 *	interface is identified with %NL80211_ATTR_IFINDEX and the management
 *	frame subtype with %NL80211_ATTR_MGMT_SUBTYPE. The extra IE data to be
 *	added to the end of the specified management frame is specified with
 *	%NL80211_ATTR_IE. If the command succeeds, the requested data will be
 *	added to all specified management frames generated by
 *	kernel/firmware/driver.
 *	Note: This command has been removed and it is only reserved at this
 *	point to avoid re-using existing command number. The functionality this
 *	command was planned for has been provided with cleaner design with the
 *	option to specify additional IEs in NL80211_CMD_TRIGGER_SCAN,
 *	NL80211_CMD_AUTHENTICATE, NL80211_CMD_ASSOCIATE,
 *	NL80211_CMD_DEAUTHENTICATE, and NL80211_CMD_DISASSOCIATE.
 *
 * @NL80211_CMD_GET_SCAN: get scan results
 * @NL80211_CMD_TRIGGER_SCAN: trigger a new scan with the given parameters
 *	%NL80211_ATTR_TX_NO_CCK_RATE is used to decide whether to send the
 *	probe requests at CCK rate or not.
 * @NL80211_CMD_NEW_SCAN_RESULTS: scan notification (as a reply to
 *	NL80211_CMD_GET_SCAN and on the "scan" multicast group)
 * @NL80211_CMD_SCAN_ABORTED: scan was aborted, for unspecified reasons,
 *	partial scan results may be available
 *
 * @NL80211_CMD_START_SCHED_SCAN: start a scheduled scan at certain
 *	intervals, as specified by %NL80211_ATTR_SCHED_SCAN_INTERVAL.
 *	Like with normal scans, if SSIDs (%NL80211_ATTR_SCAN_SSIDS)
 *	are passed, they are used in the probe requests.  For
 *	broadcast, a broadcast SSID must be passed (ie. an empty
 *	string).  If no SSID is passed, no probe requests are sent and
 *	a passive scan is performed.  %NL80211_ATTR_SCAN_FREQUENCIES,
 *	if passed, define which channels should be scanned; if not
 *	passed, all channels allowed for the current regulatory domain
 *	are used.  Extra IEs can also be passed from the userspace by
 *	using the %NL80211_ATTR_IE attribute.
 * @NL80211_CMD_STOP_SCHED_SCAN: stop a scheduled scan.  Returns -ENOENT
 *	if scheduled scan is not running.
 * @NL80211_CMD_SCHED_SCAN_RESULTS: indicates that there are scheduled scan
 *	results available.
 * @NL80211_CMD_SCHED_SCAN_STOPPED: indicates that the scheduled scan has
 *	stopped.  The driver may issue this event at any time during a
 *	scheduled scan.  One reason for stopping the scan is if the hardware
 *	does not support starting an association or a normal scan while running
 *	a scheduled scan.  This event is also sent when the
 *	%NL80211_CMD_STOP_SCHED_SCAN command is received or when the interface
 *	is brought down while a scheduled scan was running.
 *
 * @NL80211_CMD_GET_SURVEY: get survey resuls, e.g. channel occupation
 *      or noise level
 * @NL80211_CMD_NEW_SURVEY_RESULTS: survey data notification (as a reply to
 *	NL80211_CMD_GET_SURVEY and on the "scan" multicast group)
 *
 * @NL80211_CMD_SET_PMKSA: Add a PMKSA cache entry, using %NL80211_ATTR_MAC
 *	(for the BSSID) and %NL80211_ATTR_PMKID.
 * @NL80211_CMD_DEL_PMKSA: Delete a PMKSA cache entry, using %NL80211_ATTR_MAC
 *	(for the BSSID) and %NL80211_ATTR_PMKID.
 * @NL80211_CMD_FLUSH_PMKSA: Flush all PMKSA cache entries.
 *
 * @NL80211_CMD_REG_CHANGE: indicates to userspace the regulatory domain
 * 	has been changed and provides details of the request information
 * 	that caused the change such as who initiated the regulatory request
 * 	(%NL80211_ATTR_REG_INITIATOR), the wiphy_idx
 * 	(%NL80211_ATTR_REG_ALPHA2) on which the request was made from if
 * 	the initiator was %NL80211_REGDOM_SET_BY_COUNTRY_IE or
 * 	%NL80211_REGDOM_SET_BY_DRIVER, the type of regulatory domain
 * 	set (%NL80211_ATTR_REG_TYPE), if the type of regulatory domain is
 * 	%NL80211_REG_TYPE_COUNTRY the alpha2 to which we have moved on
 * 	to (%NL80211_ATTR_REG_ALPHA2).
 * @NL80211_CMD_REG_BEACON_HINT: indicates to userspace that an AP beacon
 * 	has been found while world roaming thus enabling active scan or
 * 	any mode of operation that initiates TX (beacons) on a channel
 * 	where we would not have been able to do either before. As an example
 * 	if you are world roaming (regulatory domain set to world or if your
 * 	driver is using a custom world roaming regulatory domain) and while
 * 	doing a passive scan on the 5 GHz band you find an AP there (if not
 * 	on a DFS channel) you will now be able to actively scan for that AP
 * 	or use AP mode on your card on that same channel. Note that this will
 * 	never be used for channels 1-11 on the 2 GHz band as they are always
 * 	enabled world wide. This beacon hint is only sent if your device had
 * 	either disabled active scanning or beaconing on a channel. We send to
 * 	userspace the wiphy on which we removed a restriction from
 * 	(%NL80211_ATTR_WIPHY) and the channel on which this occurred
 * 	before (%NL80211_ATTR_FREQ_BEFORE) and after (%NL80211_ATTR_FREQ_AFTER)
 * 	the beacon hint was processed.
 *
 * @NL80211_CMD_AUTHENTICATE: authentication request and notification.
 *	This command is used both as a command (request to authenticate) and
 *	as an event on the "mlme" multicast group indicating completion of the
 *	authentication process.
 *	When used as a command, %NL80211_ATTR_IFINDEX is used to identify the
 *	interface. %NL80211_ATTR_MAC is used to specify PeerSTAAddress (and
 *	BSSID in case of station mode). %NL80211_ATTR_SSID is used to specify
 *	the SSID (mainly for association, but is included in authentication
 *	request, too, to help BSS selection. %NL80211_ATTR_WIPHY_FREQ is used
 *	to specify the frequence of the channel in MHz. %NL80211_ATTR_AUTH_TYPE
 *	is used to specify the authentication type. %NL80211_ATTR_IE is used to
 *	define IEs (VendorSpecificInfo, but also including RSN IE and FT IEs)
 *	to be added to the frame.
 *	When used as an event, this reports reception of an Authentication
 *	frame in station and IBSS modes when the local MLME processed the
 *	frame, i.e., it was for the local STA and was received in correct
 *	state. This is similar to MLME-AUTHENTICATE.confirm primitive in the
 *	MLME SAP interface (kernel providing MLME, userspace SME). The
 *	included %NL80211_ATTR_FRAME attribute contains the management frame
 *	(including both the header and frame body, but not FCS). This event is
 *	also used to indicate if the authentication attempt timed out. In that
 *	case the %NL80211_ATTR_FRAME attribute is replaced with a
 *	%NL80211_ATTR_TIMED_OUT flag (and %NL80211_ATTR_MAC to indicate which
 *	pending authentication timed out).
 * @NL80211_CMD_ASSOCIATE: association request and notification; like
 *	NL80211_CMD_AUTHENTICATE but for Association and Reassociation
 *	(similar to MLME-ASSOCIATE.request, MLME-REASSOCIATE.request,
 *	MLME-ASSOCIATE.confirm or MLME-REASSOCIATE.confirm primitives).
 * @NL80211_CMD_DEAUTHENTICATE: deauthentication request and notification; like
 *	NL80211_CMD_AUTHENTICATE but for Deauthentication frames (similar to
 *	MLME-DEAUTHENTICATION.request and MLME-DEAUTHENTICATE.indication
 *	primitives).
 * @NL80211_CMD_DISASSOCIATE: disassociation request and notification; like
 *	NL80211_CMD_AUTHENTICATE but for Disassociation frames (similar to
 *	MLME-DISASSOCIATE.request and MLME-DISASSOCIATE.indication primitives).
 *
 * @NL80211_CMD_MICHAEL_MIC_FAILURE: notification of a locally detected Michael
 *	MIC (part of TKIP) failure; sent on the "mlme" multicast group; the
 *	event includes %NL80211_ATTR_MAC to describe the source MAC address of
 *	the frame with invalid MIC, %NL80211_ATTR_KEY_TYPE to show the key
 *	type, %NL80211_ATTR_KEY_IDX to indicate the key identifier, and
 *	%NL80211_ATTR_KEY_SEQ to indicate the TSC value of the frame; this
 *	event matches with MLME-MICHAELMICFAILURE.indication() primitive
 *
 * @NL80211_CMD_JOIN_IBSS: Join a new IBSS -- given at least an SSID and a
 *	FREQ attribute (for the initial frequency if no peer can be found)
 *	and optionally a MAC (as BSSID) and FREQ_FIXED attribute if those
 *	should be fixed rather than automatically determined. Can only be
 *	executed on a network interface that is UP, and fixed BSSID/FREQ
 *	may be rejected. Another optional parameter is the beacon interval,
 *	given in the %NL80211_ATTR_BEACON_INTERVAL attribute, which if not
 *	given defaults to 100 TU (102.4ms).
 * @NL80211_CMD_LEAVE_IBSS: Leave the IBSS -- no special arguments, the IBSS is
 *	determined by the network interface.
 *
 * @NL80211_CMD_TESTMODE: testmode command, takes a wiphy (or ifindex) attribute
 *	to identify the device, and the TESTDATA blob attribute to pass through
 *	to the driver.
 *
 * @NL80211_CMD_CONNECT: connection request and notification; this command
 *	requests to connect to a specified network but without separating
 *	auth and assoc steps. For this, you need to specify the SSID in a
 *	%NL80211_ATTR_SSID attribute, and can optionally specify the association
 *	IEs in %NL80211_ATTR_IE, %NL80211_ATTR_AUTH_TYPE, %NL80211_ATTR_USE_MFP,
 *	%NL80211_ATTR_MAC, %NL80211_ATTR_WIPHY_FREQ, %NL80211_ATTR_CONTROL_PORT,
 *	%NL80211_ATTR_CONTROL_PORT_ETHERTYPE and
 *	%NL80211_ATTR_CONTROL_PORT_NO_ENCRYPT.
 *	Background scan period can optionally be
 *	specified in %NL80211_ATTR_BG_SCAN_PERIOD,
 *	if not specified default background scan configuration
 *	in driver is used and if period value is 0, bg scan will be disabled.
 *	This attribute is ignored if driver does not support roam scan.
 *	It is also sent as an event, with the BSSID and response IEs when the
 *	connection is established or failed to be established. This can be
 *	determined by the STATUS_CODE attribute.
 * @NL80211_CMD_ROAM: request that the card roam (currently not implemented),
 *	sent as an event when the card/driver roamed by itself.
 * @NL80211_CMD_DISCONNECT: drop a given connection; also used to notify
 *	userspace that a connection was dropped by the AP or due to other
 *	reasons, for this the %NL80211_ATTR_DISCONNECTED_BY_AP and
 *	%NL80211_ATTR_REASON_CODE attributes are used.
 *
 * @NL80211_CMD_SET_WIPHY_NETNS: Set a wiphy's netns. Note that all devices
 *	associated with this wiphy must be down and will follow.
 *
 * @NL80211_CMD_REMAIN_ON_CHANNEL: Request to remain awake on the specified
 *	channel for the specified amount of time. This can be used to do
 *	off-channel operations like transmit a Public Action frame and wait for
 *	a response while being associated to an AP on another channel.
 *	%NL80211_ATTR_IFINDEX is used to specify which interface (and thus
 *	radio) is used. %NL80211_ATTR_WIPHY_FREQ is used to specify the
 *	frequency for the operation.
 *	%NL80211_ATTR_DURATION is used to specify the duration in milliseconds
 *	to remain on the channel. This command is also used as an event to
 *	notify when the requested duration starts (it may take a while for the
 *	driver to schedule this time due to other concurrent needs for the
 *	radio).
 *	When called, this operation returns a cookie (%NL80211_ATTR_COOKIE)
 *	that will be included with any events pertaining to this request;
 *	the cookie is also used to cancel the request.
 * @NL80211_CMD_CANCEL_REMAIN_ON_CHANNEL: This command can be used to cancel a
 *	pending remain-on-channel duration if the desired operation has been
 *	completed prior to expiration of the originally requested duration.
 *	%NL80211_ATTR_WIPHY or %NL80211_ATTR_IFINDEX is used to specify the
 *	radio. The %NL80211_ATTR_COOKIE attribute must be given as well to
 *	uniquely identify the request.
 *	This command is also used as an event to notify when a requested
 *	remain-on-channel duration has expired.
 *
 * @NL80211_CMD_SET_TX_BITRATE_MASK: Set the mask of rates to be used in TX
 *	rate selection. %NL80211_ATTR_IFINDEX is used to specify the interface
 *	and @NL80211_ATTR_TX_RATES the set of allowed rates.
 *
 * @NL80211_CMD_REGISTER_FRAME: Register for receiving certain mgmt frames
 *	(via @NL80211_CMD_FRAME) for processing in userspace. This command
 *	requires an interface index, a frame type attribute (optional for
 *	backward compatibility reasons, if not given assumes action frames)
 *	and a match attribute containing the first few bytes of the frame
 *	that should match, e.g. a single byte for only a category match or
 *	four bytes for vendor frames including the OUI. The registration
 *	cannot be dropped, but is removed automatically when the netlink
 *	socket is closed. Multiple registrations can be made.
 * @NL80211_CMD_REGISTER_ACTION: Alias for @NL80211_CMD_REGISTER_FRAME for
 *	backward compatibility
 * @NL80211_CMD_FRAME: Management frame TX request and RX notification. This
 *	command is used both as a request to transmit a management frame and
 *	as an event indicating reception of a frame that was not processed in
 *	kernel code, but is for us (i.e., which may need to be processed in a
 *	user space application). %NL80211_ATTR_FRAME is used to specify the
 *	frame contents (including header). %NL80211_ATTR_WIPHY_FREQ is used
 *	to indicate on which channel the frame is to be transmitted or was
 *	received. If this channel is not the current channel (remain-on-channel
 *	or the operational channel) the device will switch to the given channel
 *	and transmit the frame, optionally waiting for a response for the time
 *	specified using %NL80211_ATTR_DURATION. When called, this operation
 *	returns a cookie (%NL80211_ATTR_COOKIE) that will be included with the
 *	TX status event pertaining to the TX request.
 *	%NL80211_ATTR_TX_NO_CCK_RATE is used to decide whether to send the
 *	management frames at CCK rate or not in 2GHz band.
 * @NL80211_CMD_FRAME_WAIT_CANCEL: When an off-channel TX was requested, this
 *	command may be used with the corresponding cookie to cancel the wait
 *	time if it is known that it is no longer necessary.
 * @NL80211_CMD_ACTION: Alias for @NL80211_CMD_FRAME for backward compatibility.
 * @NL80211_CMD_FRAME_TX_STATUS: Report TX status of a management frame
 *	transmitted with %NL80211_CMD_FRAME. %NL80211_ATTR_COOKIE identifies
 *	the TX command and %NL80211_ATTR_FRAME includes the contents of the
 *	frame. %NL80211_ATTR_ACK flag is included if the recipient acknowledged
 *	the frame.
 * @NL80211_CMD_ACTION_TX_STATUS: Alias for @NL80211_CMD_FRAME_TX_STATUS for
 *	backward compatibility.
 *
 * @NL80211_CMD_SET_POWER_SAVE: Set powersave, using %NL80211_ATTR_PS_STATE
 * @NL80211_CMD_GET_POWER_SAVE: Get powersave status in %NL80211_ATTR_PS_STATE
 *
 * @NL80211_CMD_SET_CQM: Connection quality monitor configuration. This command
 *	is used to configure connection quality monitoring notification trigger
 *	levels.
 * @NL80211_CMD_NOTIFY_CQM: Connection quality monitor notification. This
 *	command is used as an event to indicate the that a trigger level was
 *	reached.
 * @NL80211_CMD_SET_CHANNEL: Set the channel (using %NL80211_ATTR_WIPHY_FREQ
 *	and the attributes determining channel width) the given interface
 *	(identifed by %NL80211_ATTR_IFINDEX) shall operate on.
 *	In case multiple channels are supported by the device, the mechanism
 *	with which it switches channels is implementation-defined.
 *	When a monitor interface is given, it can only switch channel while
 *	no other interfaces are operating to avoid disturbing the operation
 *	of any other interfaces, and other interfaces will again take
 *	precedence when they are used.
 *
 * @NL80211_CMD_SET_WDS_PEER: Set the MAC address of the peer on a WDS interface.
 *
 * @NL80211_CMD_JOIN_MESH: Join a mesh. The mesh ID must be given, and initial
 *	mesh config parameters may be given.
 * @NL80211_CMD_LEAVE_MESH: Leave the mesh network -- no special arguments, the
 *	network is determined by the network interface.
 *
 * @NL80211_CMD_UNPROT_DEAUTHENTICATE: Unprotected deauthentication frame
 *	notification. This event is used to indicate that an unprotected
 *	deauthentication frame was dropped when MFP is in use.
 * @NL80211_CMD_UNPROT_DISASSOCIATE: Unprotected disassociation frame
 *	notification. This event is used to indicate that an unprotected
 *	disassociation frame was dropped when MFP is in use.
 *
 * @NL80211_CMD_NEW_PEER_CANDIDATE: Notification on the reception of a
 *      beacon or probe response from a compatible mesh peer.  This is only
 *      sent while no station information (sta_info) exists for the new peer
 *      candidate and when @NL80211_MESH_SETUP_USERSPACE_AUTH,
 *      @NL80211_MESH_SETUP_USERSPACE_AMPE, or
 *      @NL80211_MESH_SETUP_USERSPACE_MPM is set.  On reception of this
 *      notification, userspace may decide to create a new station
 *      (@NL80211_CMD_NEW_STATION).  To stop this notification from
 *      reoccurring, the userspace authentication daemon may want to create the
 *      new station with the AUTHENTICATED flag unset and maybe change it later
 *      depending on the authentication result.
 *
 * @NL80211_CMD_GET_WOWLAN: get Wake-on-Wireless-LAN (WoWLAN) settings.
 * @NL80211_CMD_SET_WOWLAN: set Wake-on-Wireless-LAN (WoWLAN) settings.
 *	Since wireless is more complex than wired ethernet, it supports
 *	various triggers. These triggers can be configured through this
 *	command with the %NL80211_ATTR_WOWLAN_TRIGGERS attribute. For
 *	more background information, see
 *	http://wireless.kernel.org/en/users/Documentation/WoWLAN.
 *	The @NL80211_CMD_SET_WOWLAN command can also be used as a notification
 *	from the driver reporting the wakeup reason. In this case, the
 *	@NL80211_ATTR_WOWLAN_TRIGGERS attribute will contain the reason
 *	for the wakeup, if it was caused by wireless. If it is not present
 *	in the wakeup notification, the wireless device didn't cause the
 *	wakeup but reports that it was woken up.
 *
 * @NL80211_CMD_SET_REKEY_OFFLOAD: This command is used give the driver
 *	the necessary information for supporting GTK rekey offload. This
 *	feature is typically used during WoWLAN. The configuration data
 *	is contained in %NL80211_ATTR_REKEY_DATA (which is nested and
 *	contains the data in sub-attributes). After rekeying happened,
 *	this command may also be sent by the driver as an MLME event to
 *	inform userspace of the new replay counter.
 *
 * @NL80211_CMD_PMKSA_CANDIDATE: This is used as an event to inform userspace
 *	of PMKSA caching dandidates.
 *
 * @NL80211_CMD_TDLS_OPER: Perform a high-level TDLS command (e.g. link setup).
 *	In addition, this can be used as an event to request userspace to take
 *	actions on TDLS links (set up a new link or tear down an existing one).
 *	In such events, %NL80211_ATTR_TDLS_OPERATION indicates the requested
 *	operation, %NL80211_ATTR_MAC contains the peer MAC address, and
 *	%NL80211_ATTR_REASON_CODE the reason code to be used (only with
 *	%NL80211_TDLS_TEARDOWN).
 * @NL80211_CMD_TDLS_MGMT: Send a TDLS management frame.
 *
 * @NL80211_CMD_UNEXPECTED_FRAME: Used by an application controlling an AP
 *	(or GO) interface (i.e. hostapd) to ask for unexpected frames to
 *	implement sending deauth to stations that send unexpected class 3
 *	frames. Also used as the event sent by the kernel when such a frame
 *	is received.
 *	For the event, the %NL80211_ATTR_MAC attribute carries the TA and
 *	other attributes like the interface index are present.
 *	If used as the command it must have an interface index and you can
 *	only unsubscribe from the event by closing the socket. Subscription
 *	is also for %NL80211_CMD_UNEXPECTED_4ADDR_FRAME events.
 *
 * @NL80211_CMD_UNEXPECTED_4ADDR_FRAME: Sent as an event indicating that the
 *	associated station identified by %NL80211_ATTR_MAC sent a 4addr frame
 *	and wasn't already in a 4-addr VLAN. The event will be sent similarly
 *	to the %NL80211_CMD_UNEXPECTED_FRAME event, to the same listener.
 *
 * @NL80211_CMD_PROBE_CLIENT: Probe an associated station on an AP interface
 *	by sending a null data frame to it and reporting when the frame is
 *	acknowleged. This is used to allow timing out inactive clients. Uses
 *	%NL80211_ATTR_IFINDEX and %NL80211_ATTR_MAC. The command returns a
 *	direct reply with an %NL80211_ATTR_COOKIE that is later used to match
 *	up the event with the request. The event includes the same data and
 *	has %NL80211_ATTR_ACK set if the frame was ACKed.
 *
 * @NL80211_CMD_REGISTER_BEACONS: Register this socket to receive beacons from
 *	other BSSes when any interfaces are in AP mode. This helps implement
 *	OLBC handling in hostapd. Beacons are reported in %NL80211_CMD_FRAME
 *	messages. Note that per PHY only one application may register.
 *
 * @NL80211_CMD_SET_NOACK_MAP: sets a bitmap for the individual TIDs whether
 *      No Acknowledgement Policy should be applied.
 *
 * @NL80211_CMD_CH_SWITCH_NOTIFY: An AP or GO may decide to switch channels
 *	independently of the userspace SME, send this event indicating
 *	%NL80211_ATTR_IFINDEX is now on %NL80211_ATTR_WIPHY_FREQ and the
 *	attributes determining channel width.
 *
 * @NL80211_CMD_START_P2P_DEVICE: Start the given P2P Device, identified by
 *	its %NL80211_ATTR_WDEV identifier. It must have been created with
 *	%NL80211_CMD_NEW_INTERFACE previously. After it has been started, the
 *	P2P Device can be used for P2P operations, e.g. remain-on-channel and
 *	public action frame TX.
 * @NL80211_CMD_STOP_P2P_DEVICE: Stop the given P2P Device, identified by
 *	its %NL80211_ATTR_WDEV identifier.
 *
 * @NL80211_CMD_CONN_FAILED: connection request to an AP failed; used to
 *	notify userspace that AP has rejected the connection request from a
 *	station, due to particular reason. %NL80211_ATTR_CONN_FAILED_REASON
 *	is used for this.
 *
 * @NL80211_CMD_SET_MCAST_RATE: Change the rate used to send multicast frames
 *	for IBSS or MESH vif.
 *
 * @NL80211_CMD_SET_MAC_ACL: sets ACL for MAC address based access control.
 *	This is to be used with the drivers advertising the support of MAC
 *	address based access control. List of MAC addresses is passed in
 *	%NL80211_ATTR_MAC_ADDRS and ACL policy is passed in
 *	%NL80211_ATTR_ACL_POLICY. Driver will enable ACL with this list, if it
 *	is not already done. The new list will replace any existing list. Driver
 *	will clear its ACL when the list of MAC addresses passed is empty. This
 *	command is used in AP/P2P GO mode. Driver has to make sure to clear its
 *	ACL list during %NL80211_CMD_STOP_AP.
 *
 * @NL80211_CMD_RADAR_DETECT: Start a Channel availability check (CAC). Once
 *	a radar is detected or the channel availability scan (CAC) has finished
 *	or was aborted, or a radar was detected, usermode will be notified with
 *	this event. This command is also used to notify userspace about radars
 *	while operating on this channel.
 *	%NL80211_ATTR_RADAR_EVENT is used to inform about the type of the
 *	event.
 *
 * @NL80211_CMD_GET_PROTOCOL_FEATURES: Get global nl80211 protocol features,
 *	i.e. features for the nl80211 protocol rather than device features.
 *	Returns the features in the %NL80211_ATTR_PROTOCOL_FEATURES bitmap.
 *
 * @NL80211_CMD_UPDATE_FT_IES: Pass down the most up-to-date Fast Transition
 *	Information Element to the WLAN driver
 *
 * @NL80211_CMD_FT_EVENT: Send a Fast transition event from the WLAN driver
 *	to the supplicant. This will carry the target AP's MAC address along
 *	with the relevant Information Elements. This event is used to report
 *	received FT IEs (MDIE, FTIE, RSN IE, TIE, RICIE).
 *
 * @NL80211_CMD_CRIT_PROTOCOL_START: Indicates user-space will start running
 *	a critical protocol that needs more reliability in the connection to
 *	complete.
 *
 * @NL80211_CMD_CRIT_PROTOCOL_STOP: Indicates the connection reliability can
 *	return back to normal.
 *
 * @NL80211_CMD_GET_COALESCE: Get currently supported coalesce rules.
 * @NL80211_CMD_SET_COALESCE: Configure coalesce rules or clear existing rules.
 *
 * @NL80211_CMD_CHANNEL_SWITCH: Perform a channel switch by announcing the
 *	the new channel information (Channel Switch Announcement - CSA)
 *	in the beacon for some time (as defined in the
 *	%NL80211_ATTR_CH_SWITCH_COUNT parameter) and then change to the
 *	new channel. Userspace provides the new channel information (using
 *	%NL80211_ATTR_WIPHY_FREQ and the attributes determining channel
 *	width). %NL80211_ATTR_CH_SWITCH_BLOCK_TX may be supplied to inform
 *	other station that transmission must be blocked until the channel
 *	switch is complete.
 *
 * @NL80211_CMD_MAX: highest used command number
 * @__NL80211_CMD_AFTER_LAST: internal use
 */
"""
NL80211_CMD_UNSPEC                   =   0
NL80211_CMD_GET_WIPHY                =   1
NL80211_CMD_SET_WIPHY                =   2
NL80211_CMD_NEW_WIPHY                =   3
NL80211_CMD_DEL_WIPHY                =   4
NL80211_CMD_GET_INTERFACE            =   5
NL80211_CMD_SET_INTERFACE            =   6
NL80211_CMD_NEW_INTERFACE            =   7
NL80211_CMD_DEL_INTERFACE            =   8
NL80211_CMD_GET_KEY                  =   9
NL80211_CMD_SET_KEY                  =  10
NL80211_CMD_NEW_KEY                  =  11
NL80211_CMD_DEL_KEY                  =  12
NL80211_CMD_GET_BEACON               =  13
NL80211_CMD_SET_BEACON               =  14
NL80211_CMD_START_AP                 =  15
NL80211_CMD_NEW_BEACON = NL80211_CMD_START_AP
NL80211_CMD_STOP_AP                  =  16
NL80211_CMD_DEL_BEACON = NL80211_CMD_STOP_AP
NL80211_CMD_GET_STATION              =  17
NL80211_CMD_SET_STATION              =  18
NL80211_CMD_NEW_STATION              =  19
NL80211_CMD_DEL_STATION              =  20
NL80211_CMD_GET_MPATH                =  21
NL80211_CMD_SET_MPATH                =  22
NL80211_CMD_NEW_MPATH                =  23
NL80211_CMD_DEL_MPATH                =  24
NL80211_CMD_SET_BSS                  =  25
NL80211_CMD_SET_REG                  =  26
NL80211_CMD_REQ_SET_REG              =  27
NL80211_CMD_GET_MESH_CONFIG          =  28
NL80211_CMD_SET_MESH_CONFIG          =  29
NL80211_CMD_SET_MGMT_EXTRA_IE        =  30 # reserved; not used
NL80211_CMD_GET_REG                  =  31
NL80211_CMD_GET_SCAN                 =  32
NL80211_CMD_TRIGGER_SCAN             =  33
NL80211_CMD_NEW_SCAN_RESULTS         =  34
NL80211_CMD_SCAN_ABORTED             =  35
NL80211_CMD_REG_CHANGE               =  36
NL80211_CMD_AUTHENTICATE             =  37
NL80211_CMD_ASSOCIATE                =  38
NL80211_CMD_DEAUTHENTICATE           =  39
NL80211_CMD_DISASSOCIATE             =  40
NL80211_CMD_MICHAEL_MIC_FAILURE      =  41
NL80211_CMD_REG_BEACON_HINT          =  42
NL80211_CMD_JOIN_IBSS                =  43
NL80211_CMD_LEAVE_IBSS               =  44
NL80211_CMD_TESTMODE                 =  45
NL80211_CMD_CONNECT                  =  46
NL80211_CMD_ROAM                     =  47
NL80211_CMD_DISCONNECT               =  48
NL80211_CMD_SET_WIPHY_NETNS          =  49
NL80211_CMD_GET_SURVEY               =  50
NL80211_CMD_NEW_SURVEY_RESULTS       =  51
NL80211_CMD_SET_PMKSA                =  52
NL80211_CMD_DEL_PMKSA                =  53
NL80211_CMD_FLUSH_PMKSA              =  54
NL80211_CMD_REMAIN_ON_CHANNEL        =  55
NL80211_CMD_CANCEL_REMAIN_ON_CHANNEL =  56
NL80211_CMD_SET_TX_BITRATE_MASK      =  57
NL80211_CMD_REGISTER_FRAME           =  58
NL80211_CMD_REGISTER_ACTION = NL80211_CMD_REGISTER_FRAME
NL80211_CMD_FRAME                    =  59
NL80211_CMD_ACTION = NL80211_CMD_FRAME
NL80211_CMD_FRAME_TX_STATUS          =  60
NL80211_CMD_ACTION_TX_STATUS = NL80211_CMD_FRAME_TX_STATUS
NL80211_CMD_SET_POWER_SAVE           =  61
NL80211_CMD_GET_POWER_SAVE           =  62
NL80211_CMD_SET_CQM                  =  63
NL80211_CMD_NOTIFY_CQM               =  64
NL80211_CMD_SET_CHANNEL              =  65
NL80211_CMD_SET_WDS_PEER             =  66
NL80211_CMD_FRAME_WAIT_CANCEL        =  67
NL80211_CMD_JOIN_MESH                =  68
NL80211_CMD_LEAVE_MESH               =  69
NL80211_CMD_UNPROT_DEAUTHENTICATE    =  70
NL80211_CMD_UNPROT_DISASSOCIATE      =  71
NL80211_CMD_NEW_PEER_CANDIDATE       =  72
NL80211_CMD_GET_WOWLAN               =  73
NL80211_CMD_SET_WOWLAN               =  74
NL80211_CMD_START_SCHED_SCAN         =  75
NL80211_CMD_STOP_SCHED_SCAN          =  76
NL80211_CMD_SCHED_SCAN_RESULTS       =  77
NL80211_CMD_SCHED_SCAN_STOPPED       =  78
NL80211_CMD_SET_REKEY_OFFLOAD        =  79
NL80211_CMD_PMKSA_CANDIDATE          =  80
NL80211_CMD_TDLS_OPER                =  81
NL80211_CMD_TDLS_MGMT                =  82
NL80211_CMD_UNEXPECTED_FRAME         =  83
NL80211_CMD_PROBE_CLIENT             =  84
NL80211_CMD_REGISTER_BEACONS         =  85
NL80211_CMD_UNEXPECTED_4ADDR_FRAME   =  86
NL80211_CMD_SET_NOACK_MAP            =  87
NL80211_CMD_CH_SWITCH_NOTIFY         =  88
NL80211_CMD_START_P2P_DEVICE         =  89
NL80211_CMD_STOP_P2P_DEVICE          =  90
NL80211_CMD_CONN_FAILED              =  91
NL80211_CMD_SET_MCAST_RATE           =  92
NL80211_CMD_SET_MAC_ACL              =  93
NL80211_CMD_RADAR_DETECT             =  94
NL80211_CMD_GET_PROTOCOL_FEATURES    =  95
NL80211_CMD_UPDATE_FT_IES            =  96
NL80211_CMD_FT_EVENT                 =  97
NL80211_CMD_CRIT_PROTOCOL_START      =  98
NL80211_CMD_CRIT_PROTOCOL_STOP       =  99
NL80211_CMD_GET_COALESCE             = 100
NL80211_CMD_SET_COALESCE             = 101
NL80211_CMD_CHANNEL_SWITCH           = 102
# add new commands above here
# used to define NL80211_CMD_MAX below
__NL80211_CMD_AFTER_LAST             = 103
NL80211_CMD_MAX = __NL80211_CMD_AFTER_LAST - 1

# source-level API compatibility
NL80211_CMD_GET_MESH_PARAMS           = NL80211_CMD_GET_MESH_CONFIG
NL80211_CMD_SET_MESH_PARAMS           = NL80211_CMD_SET_MESH_CONFIG
#NL80211_MESH_SETUP_VENDOR_PATH_SEL_IE = NL80211_MESH_SETUP_IE

"""
/**
 * enum nl80211_attrs - nl80211 netlink attributes
 *
 * @NL80211_ATTR_UNSPEC: unspecified attribute to catch errors
 *
 * @NL80211_ATTR_WIPHY: index of wiphy to operate on, cf.
 *	/sys/class/ieee80211/<phyname>/index
 * @NL80211_ATTR_WIPHY_NAME: wiphy name (used for renaming)
 * @NL80211_ATTR_WIPHY_TXQ_PARAMS: a nested array of TX queue parameters
 * @NL80211_ATTR_WIPHY_FREQ: frequency of the selected channel in MHz,
 *	defines the channel together with the (deprecated)
 *	%NL80211_ATTR_WIPHY_CHANNEL_TYPE attribute or the attributes
 *	%NL80211_ATTR_CHANNEL_WIDTH and if needed %NL80211_ATTR_CENTER_FREQ1
 *	and %NL80211_ATTR_CENTER_FREQ2
 * @NL80211_ATTR_CHANNEL_WIDTH: u32 attribute containing one of the values
 *	of &enum nl80211_chan_width, describing the channel width. See the
 *	documentation of the enum for more information.
 * @NL80211_ATTR_CENTER_FREQ1: Center frequency of the first part of the
 *	channel, used for anything but 20 MHz bandwidth
 * @NL80211_ATTR_CENTER_FREQ2: Center frequency of the second part of the
 *	channel, used only for 80+80 MHz bandwidth
 * @NL80211_ATTR_WIPHY_CHANNEL_TYPE: included with NL80211_ATTR_WIPHY_FREQ
 *	if HT20 or HT40 are to be used (i.e., HT disabled if not included):
 *	NL80211_CHAN_NO_HT = HT not allowed (i.e., same as not including
 *		this attribute)
 *	NL80211_CHAN_HT20 = HT20 only
 *	NL80211_CHAN_HT40MINUS = secondary channel is below the primary channel
 *	NL80211_CHAN_HT40PLUS = secondary channel is above the primary channel
 *	This attribute is now deprecated.
 * @NL80211_ATTR_WIPHY_RETRY_SHORT: TX retry limit for frames whose length is
 *	less than or equal to the RTS threshold; allowed range: 1..255;
 *	dot11ShortRetryLimit; u8
 * @NL80211_ATTR_WIPHY_RETRY_LONG: TX retry limit for frames whose length is
 *	greater than the RTS threshold; allowed range: 1..255;
 *	dot11ShortLongLimit; u8
 * @NL80211_ATTR_WIPHY_FRAG_THRESHOLD: fragmentation threshold, i.e., maximum
 *	length in octets for frames; allowed range: 256..8000, disable
 *	fragmentation with (u32)-1; dot11FragmentationThreshold; u32
 * @NL80211_ATTR_WIPHY_RTS_THRESHOLD: RTS threshold (TX frames with length
 *	larger than or equal to this use RTS/CTS handshake); allowed range:
 *	0..65536, disable with (u32)-1; dot11RTSThreshold; u32
 * @NL80211_ATTR_WIPHY_COVERAGE_CLASS: Coverage Class as defined by IEEE 802.11
 *	section 7.3.2.9; dot11CoverageClass; u8
 *
 * @NL80211_ATTR_IFINDEX: network interface index of the device to operate on
 * @NL80211_ATTR_IFNAME: network interface name
 * @NL80211_ATTR_IFTYPE: type of virtual interface, see &enum nl80211_iftype
 *
 * @NL80211_ATTR_WDEV: wireless device identifier, used for pseudo-devices
 *	that don't have a netdev (u64)
 *
 * @NL80211_ATTR_MAC: MAC address (various uses)
 *
 * @NL80211_ATTR_KEY_DATA: (temporal) key data; for TKIP this consists of
 *	16 bytes encryption key followed by 8 bytes each for TX and RX MIC
 *	keys
 * @NL80211_ATTR_KEY_IDX: key ID (u8, 0-3)
 * @NL80211_ATTR_KEY_CIPHER: key cipher suite (u32, as defined by IEEE 802.11
 *	section 7.3.2.25.1, e.g. 0x000FAC04)
 * @NL80211_ATTR_KEY_SEQ: transmit key sequence number (IV/PN) for TKIP and
 *	CCMP keys, each six bytes in little endian
 * @NL80211_ATTR_KEY_DEFAULT: Flag attribute indicating the key is default key
 * @NL80211_ATTR_KEY_DEFAULT_MGMT: Flag attribute indicating the key is the
 *	default management key
 * @NL80211_ATTR_CIPHER_SUITES_PAIRWISE: For crypto settings for connect or
 *	other commands, indicates which pairwise cipher suites are used
 * @NL80211_ATTR_CIPHER_SUITE_GROUP: For crypto settings for connect or
 *	other commands, indicates which group cipher suite is used
 *
 * @NL80211_ATTR_BEACON_INTERVAL: beacon interval in TU
 * @NL80211_ATTR_DTIM_PERIOD: DTIM period for beaconing
 * @NL80211_ATTR_BEACON_HEAD: portion of the beacon before the TIM IE
 * @NL80211_ATTR_BEACON_TAIL: portion of the beacon after the TIM IE
 *
 * @NL80211_ATTR_STA_AID: Association ID for the station (u16)
 * @NL80211_ATTR_STA_FLAGS: flags, nested element with NLA_FLAG attributes of
 *	&enum nl80211_sta_flags (deprecated, use %NL80211_ATTR_STA_FLAGS2)
 * @NL80211_ATTR_STA_LISTEN_INTERVAL: listen interval as defined by
 *	IEEE 802.11 7.3.1.6 (u16).
 * @NL80211_ATTR_STA_SUPPORTED_RATES: supported rates, array of supported
 *	rates as defined by IEEE 802.11 7.3.2.2 but without the length
 *	restriction (at most %NL80211_MAX_SUPP_RATES).
 * @NL80211_ATTR_STA_VLAN: interface index of VLAN interface to move station
 *	to, or the AP interface the station was originally added to to.
 * @NL80211_ATTR_STA_INFO: information about a station, part of station info
 *	given for %NL80211_CMD_GET_STATION, nested attribute containing
 *	info as possible, see &enum nl80211_sta_info.
 *
 * @NL80211_ATTR_WIPHY_BANDS: Information about an operating bands,
 *	consisting of a nested array.
 *
 * @NL80211_ATTR_MESH_ID: mesh id (1-32 bytes).
 * @NL80211_ATTR_STA_PLINK_ACTION: action to perform on the mesh peer link
 *	(see &enum nl80211_plink_action).
 * @NL80211_ATTR_MPATH_NEXT_HOP: MAC address of the next hop for a mesh path.
 * @NL80211_ATTR_MPATH_INFO: information about a mesh_path, part of mesh path
 * 	info given for %NL80211_CMD_GET_MPATH, nested attribute described at
 *	&enum nl80211_mpath_info.
 *
 * @NL80211_ATTR_MNTR_FLAGS: flags, nested element with NLA_FLAG attributes of
 *      &enum nl80211_mntr_flags.
 *
 * @NL80211_ATTR_REG_ALPHA2: an ISO-3166-alpha2 country code for which the
 * 	current regulatory domain should be set to or is already set to.
 * 	For example, 'CR', for Costa Rica. This attribute is used by the kernel
 * 	to query the CRDA to retrieve one regulatory domain. This attribute can
 * 	also be used by userspace to query the kernel for the currently set
 * 	regulatory domain. We chose an alpha2 as that is also used by the
 * 	IEEE-802.11 country information element to identify a country.
 * 	Users can also simply ask the wireless core to set regulatory domain
 * 	to a specific alpha2.
 * @NL80211_ATTR_REG_RULES: a nested array of regulatory domain regulatory
 *	rules.
 *
 * @NL80211_ATTR_BSS_CTS_PROT: whether CTS protection is enabled (u8, 0 or 1)
 * @NL80211_ATTR_BSS_SHORT_PREAMBLE: whether short preamble is enabled
 *	(u8, 0 or 1)
 * @NL80211_ATTR_BSS_SHORT_SLOT_TIME: whether short slot time enabled
 *	(u8, 0 or 1)
 * @NL80211_ATTR_BSS_BASIC_RATES: basic rates, array of basic
 *	rates in format defined by IEEE 802.11 7.3.2.2 but without the length
 *	restriction (at most %NL80211_MAX_SUPP_RATES).
 *
 * @NL80211_ATTR_HT_CAPABILITY: HT Capability information element (from
 *	association request when used with NL80211_CMD_NEW_STATION)
 *
 * @NL80211_ATTR_SUPPORTED_IFTYPES: nested attribute containing all
 *	supported interface types, each a flag attribute with the number
 *	of the interface mode.
 *
 * @NL80211_ATTR_MGMT_SUBTYPE: Management frame subtype for
 *	%NL80211_CMD_SET_MGMT_EXTRA_IE.
 *
 * @NL80211_ATTR_IE: Information element(s) data (used, e.g., with
 *	%NL80211_CMD_SET_MGMT_EXTRA_IE).
 *
 * @NL80211_ATTR_MAX_NUM_SCAN_SSIDS: number of SSIDs you can scan with
 *	a single scan request, a wiphy attribute.
 * @NL80211_ATTR_MAX_NUM_SCHED_SCAN_SSIDS: number of SSIDs you can
 *	scan with a single scheduled scan request, a wiphy attribute.
 * @NL80211_ATTR_MAX_SCAN_IE_LEN: maximum length of information elements
 *	that can be added to a scan request
 * @NL80211_ATTR_MAX_SCHED_SCAN_IE_LEN: maximum length of information
 *	elements that can be added to a scheduled scan request
 * @NL80211_ATTR_MAX_MATCH_SETS: maximum number of sets that can be
 *	used with @NL80211_ATTR_SCHED_SCAN_MATCH, a wiphy attribute.
 *
 * @NL80211_ATTR_SCAN_FREQUENCIES: nested attribute with frequencies (in MHz)
 * @NL80211_ATTR_SCAN_SSIDS: nested attribute with SSIDs, leave out for passive
 *	scanning and include a zero-length SSID (wildcard) for wildcard scan
 * @NL80211_ATTR_BSS: scan result BSS
 *
 * @NL80211_ATTR_REG_INITIATOR: indicates who requested the regulatory domain
 * 	currently in effect. This could be any of the %NL80211_REGDOM_SET_BY_*
 * @NL80211_ATTR_REG_TYPE: indicates the type of the regulatory domain currently
 * 	set. This can be one of the nl80211_reg_type (%NL80211_REGDOM_TYPE_*)
 *
 * @NL80211_ATTR_SUPPORTED_COMMANDS: wiphy attribute that specifies
 *	an array of command numbers (i.e. a mapping index to command number)
 *	that the driver for the given wiphy supports.
 *
 * @NL80211_ATTR_FRAME: frame data (binary attribute), including frame header
 *	and body, but not FCS; used, e.g., with NL80211_CMD_AUTHENTICATE and
 *	NL80211_CMD_ASSOCIATE events
 * @NL80211_ATTR_SSID: SSID (binary attribute, 0..32 octets)
 * @NL80211_ATTR_AUTH_TYPE: AuthenticationType, see &enum nl80211_auth_type,
 *	represented as a u32
 * @NL80211_ATTR_REASON_CODE: ReasonCode for %NL80211_CMD_DEAUTHENTICATE and
 *	%NL80211_CMD_DISASSOCIATE, u16
 *
 * @NL80211_ATTR_KEY_TYPE: Key Type, see &enum nl80211_key_type, represented as
 *	a u32
 *
 * @NL80211_ATTR_FREQ_BEFORE: A channel which has suffered a regulatory change
 * 	due to considerations from a beacon hint. This attribute reflects
 * 	the state of the channel _before_ the beacon hint processing. This
 * 	attributes consists of a nested attribute containing
 * 	NL80211_FREQUENCY_ATTR_*
 * @NL80211_ATTR_FREQ_AFTER: A channel which has suffered a regulatory change
 * 	due to considerations from a beacon hint. This attribute reflects
 * 	the state of the channel _after_ the beacon hint processing. This
 * 	attributes consists of a nested attribute containing
 * 	NL80211_FREQUENCY_ATTR_*
 *
 * @NL80211_ATTR_CIPHER_SUITES: a set of u32 values indicating the supported
 *	cipher suites
 *
 * @NL80211_ATTR_FREQ_FIXED: a flag indicating the IBSS should not try to look
 *	for other networks on different channels
 *
 * @NL80211_ATTR_TIMED_OUT: a flag indicating than an operation timed out; this
 *	is used, e.g., with %NL80211_CMD_AUTHENTICATE event
 *
 * @NL80211_ATTR_USE_MFP: Whether management frame protection (IEEE 802.11w) is
 *	used for the association (&enum nl80211_mfp, represented as a u32);
 *	this attribute can be used
 *	with %NL80211_CMD_ASSOCIATE and %NL80211_CMD_CONNECT requests
 *
 * @NL80211_ATTR_STA_FLAGS2: Attribute containing a
 *	&struct nl80211_sta_flag_update.
 *
 * @NL80211_ATTR_CONTROL_PORT: A flag indicating whether user space controls
 *	IEEE 802.1X port, i.e., sets/clears %NL80211_STA_FLAG_AUTHORIZED, in
 *	station mode. If the flag is included in %NL80211_CMD_ASSOCIATE
 *	request, the driver will assume that the port is unauthorized until
 *	authorized by user space. Otherwise, port is marked authorized by
 *	default in station mode.
 * @NL80211_ATTR_CONTROL_PORT_ETHERTYPE: A 16-bit value indicating the
 *	ethertype that will be used for key negotiation. It can be
 *	specified with the associate and connect commands. If it is not
 *	specified, the value defaults to 0x888E (PAE, 802.1X). This
 *	attribute is also used as a flag in the wiphy information to
 *	indicate that protocols other than PAE are supported.
 * @NL80211_ATTR_CONTROL_PORT_NO_ENCRYPT: When included along with
 *	%NL80211_ATTR_CONTROL_PORT_ETHERTYPE, indicates that the custom
 *	ethertype frames used for key negotiation must not be encrypted.
 *
 * @NL80211_ATTR_TESTDATA: Testmode data blob, passed through to the driver.
 *	We recommend using nested, driver-specific attributes within this.
 *
 * @NL80211_ATTR_DISCONNECTED_BY_AP: A flag indicating that the DISCONNECT
 *	event was due to the AP disconnecting the station, and not due to
 *	a local disconnect request.
 * @NL80211_ATTR_STATUS_CODE: StatusCode for the %NL80211_CMD_CONNECT
 *	event (u16)
 * @NL80211_ATTR_PRIVACY: Flag attribute, used with connect(), indicating
 *	that protected APs should be used. This is also used with NEW_BEACON to
 *	indicate that the BSS is to use protection.
 *
 * @NL80211_ATTR_CIPHERS_PAIRWISE: Used with CONNECT, ASSOCIATE, and NEW_BEACON
 *	to indicate which unicast key ciphers will be used with the connection
 *	(an array of u32).
 * @NL80211_ATTR_CIPHER_GROUP: Used with CONNECT, ASSOCIATE, and NEW_BEACON to
 *	indicate which group key cipher will be used with the connection (a
 *	u32).
 * @NL80211_ATTR_WPA_VERSIONS: Used with CONNECT, ASSOCIATE, and NEW_BEACON to
 *	indicate which WPA version(s) the AP we want to associate with is using
 *	(a u32 with flags from &enum nl80211_wpa_versions).
 * @NL80211_ATTR_AKM_SUITES: Used with CONNECT, ASSOCIATE, and NEW_BEACON to
 *	indicate which key management algorithm(s) to use (an array of u32).
 *
 * @NL80211_ATTR_REQ_IE: (Re)association request information elements as
 *	sent out by the card, for ROAM and successful CONNECT events.
 * @NL80211_ATTR_RESP_IE: (Re)association response information elements as
 *	sent by peer, for ROAM and successful CONNECT events.
 *
 * @NL80211_ATTR_PREV_BSSID: previous BSSID, to be used by in ASSOCIATE
 *	commands to specify using a reassociate frame
 *
 * @NL80211_ATTR_KEY: key information in a nested attribute with
 *	%NL80211_KEY_* sub-attributes
 * @NL80211_ATTR_KEYS: array of keys for static WEP keys for connect()
 *	and join_ibss(), key information is in a nested attribute each
 *	with %NL80211_KEY_* sub-attributes
 *
 * @NL80211_ATTR_PID: Process ID of a network namespace.
 *
 * @NL80211_ATTR_GENERATION: Used to indicate consistent snapshots for
 *	dumps. This number increases whenever the object list being
 *	dumped changes, and as such userspace can verify that it has
 *	obtained a complete and consistent snapshot by verifying that
 *	all dump messages contain the same generation number. If it
 *	changed then the list changed and the dump should be repeated
 *	completely from scratch.
 *
 * @NL80211_ATTR_4ADDR: Use 4-address frames on a virtual interface
 *
 * @NL80211_ATTR_SURVEY_INFO: survey information about a channel, part of
 *      the survey response for %NL80211_CMD_GET_SURVEY, nested attribute
 *      containing info as possible, see &enum survey_info.
 *
 * @NL80211_ATTR_PMKID: PMK material for PMKSA caching.
 * @NL80211_ATTR_MAX_NUM_PMKIDS: maximum number of PMKIDs a firmware can
 *	cache, a wiphy attribute.
 *
 * @NL80211_ATTR_DURATION: Duration of an operation in milliseconds, u32.
 * @NL80211_ATTR_MAX_REMAIN_ON_CHANNEL_DURATION: Device attribute that
 *	specifies the maximum duration that can be requested with the
 *	remain-on-channel operation, in milliseconds, u32.
 *
 * @NL80211_ATTR_COOKIE: Generic 64-bit cookie to identify objects.
 *
 * @NL80211_ATTR_TX_RATES: Nested set of attributes
 *	(enum nl80211_tx_rate_attributes) describing TX rates per band. The
 *	enum nl80211_band value is used as the index (nla_type() of the nested
 *	data. If a band is not included, it will be configured to allow all
 *	rates based on negotiated supported rates information. This attribute
 *	is used with %NL80211_CMD_SET_TX_BITRATE_MASK.
 *
 * @NL80211_ATTR_FRAME_MATCH: A binary attribute which typically must contain
 *	at least one byte, currently used with @NL80211_CMD_REGISTER_FRAME.
 * @NL80211_ATTR_FRAME_TYPE: A u16 indicating the frame type/subtype for the
 *	@NL80211_CMD_REGISTER_FRAME command.
 * @NL80211_ATTR_TX_FRAME_TYPES: wiphy capability attribute, which is a
 *	nested attribute of %NL80211_ATTR_FRAME_TYPE attributes, containing
 *	information about which frame types can be transmitted with
 *	%NL80211_CMD_FRAME.
 * @NL80211_ATTR_RX_FRAME_TYPES: wiphy capability attribute, which is a
 *	nested attribute of %NL80211_ATTR_FRAME_TYPE attributes, containing
 *	information about which frame types can be registered for RX.
 *
 * @NL80211_ATTR_ACK: Flag attribute indicating that the frame was
 *	acknowledged by the recipient.
 *
 * @NL80211_ATTR_PS_STATE: powersave state, using &enum nl80211_ps_state values.
 *
 * @NL80211_ATTR_CQM: connection quality monitor configuration in a
 *	nested attribute with %NL80211_ATTR_CQM_* sub-attributes.
 *
 * @NL80211_ATTR_LOCAL_STATE_CHANGE: Flag attribute to indicate that a command
 *	is requesting a local authentication/association state change without
 *	invoking actual management frame exchange. This can be used with
 *	NL80211_CMD_AUTHENTICATE, NL80211_CMD_DEAUTHENTICATE,
 *	NL80211_CMD_DISASSOCIATE.
 *
 * @NL80211_ATTR_AP_ISOLATE: (AP mode) Do not forward traffic between stations
 *	connected to this BSS.
 *
 * @NL80211_ATTR_WIPHY_TX_POWER_SETTING: Transmit power setting type. See
 *      &enum nl80211_tx_power_setting for possible values.
 * @NL80211_ATTR_WIPHY_TX_POWER_LEVEL: Transmit power level in signed mBm units.
 *      This is used in association with @NL80211_ATTR_WIPHY_TX_POWER_SETTING
 *      for non-automatic settings.
 *
 * @NL80211_ATTR_SUPPORT_IBSS_RSN: The device supports IBSS RSN, which mostly
 *	means support for per-station GTKs.
 *
 * @NL80211_ATTR_WIPHY_ANTENNA_TX: Bitmap of allowed antennas for transmitting.
 *	This can be used to mask out antennas which are not attached or should
 *	not be used for transmitting. If an antenna is not selected in this
 *	bitmap the hardware is not allowed to transmit on this antenna.
 *
 *	Each bit represents one antenna, starting with antenna 1 at the first
 *	bit. Depending on which antennas are selected in the bitmap, 802.11n
 *	drivers can derive which chainmasks to use (if all antennas belonging to
 *	a particular chain are disabled this chain should be disabled) and if
 *	a chain has diversity antennas wether diversity should be used or not.
 *	HT capabilities (STBC, TX Beamforming, Antenna selection) can be
 *	derived from the available chains after applying the antenna mask.
 *	Non-802.11n drivers can derive wether to use diversity or not.
 *	Drivers may reject configurations or RX/TX mask combinations they cannot
 *	support by returning -EINVAL.
 *
 * @NL80211_ATTR_WIPHY_ANTENNA_RX: Bitmap of allowed antennas for receiving.
 *	This can be used to mask out antennas which are not attached or should
 *	not be used for receiving. If an antenna is not selected in this bitmap
 *	the hardware should not be configured to receive on this antenna.
 *	For a more detailed description see @NL80211_ATTR_WIPHY_ANTENNA_TX.
 *
 * @NL80211_ATTR_WIPHY_ANTENNA_AVAIL_TX: Bitmap of antennas which are available
 *	for configuration as TX antennas via the above parameters.
 *
 * @NL80211_ATTR_WIPHY_ANTENNA_AVAIL_RX: Bitmap of antennas which are available
 *	for configuration as RX antennas via the above parameters.
 *
 * @NL80211_ATTR_MCAST_RATE: Multicast tx rate (in 100 kbps) for IBSS
 *
 * @NL80211_ATTR_OFFCHANNEL_TX_OK: For management frame TX, the frame may be
 *	transmitted on another channel when the channel given doesn't match
 *	the current channel. If the current channel doesn't match and this
 *	flag isn't set, the frame will be rejected. This is also used as an
 *	nl80211 capability flag.
 *
 * @NL80211_ATTR_BSS_HT_OPMODE: HT operation mode (u16)
 *
 * @NL80211_ATTR_KEY_DEFAULT_TYPES: A nested attribute containing flags
 *	attributes, specifying what a key should be set as default as.
 *	See &enum nl80211_key_default_types.
 *
 * @NL80211_ATTR_MESH_SETUP: Optional mesh setup parameters.  These cannot be
 *	changed once the mesh is active.
 * @NL80211_ATTR_MESH_CONFIG: Mesh configuration parameters, a nested attribute
 *	containing attributes from &enum nl80211_meshconf_params.
 * @NL80211_ATTR_SUPPORT_MESH_AUTH: Currently, this means the underlying driver
 *	allows auth frames in a mesh to be passed to userspace for processing via
 *	the @NL80211_MESH_SETUP_USERSPACE_AUTH flag.
 * @NL80211_ATTR_STA_PLINK_STATE: The state of a mesh peer link as defined in
 *	&enum nl80211_plink_state. Used when userspace is driving the peer link
 *	management state machine.  @NL80211_MESH_SETUP_USERSPACE_AMPE or
 *	@NL80211_MESH_SETUP_USERSPACE_MPM must be enabled.
 *
 * @NL80211_ATTR_WOWLAN_TRIGGERS_SUPPORTED: indicates, as part of the wiphy
 *	capabilities, the supported WoWLAN triggers
 * @NL80211_ATTR_WOWLAN_TRIGGERS: used by %NL80211_CMD_SET_WOWLAN to
 *	indicate which WoW triggers should be enabled. This is also
 *	used by %NL80211_CMD_GET_WOWLAN to get the currently enabled WoWLAN
 *	triggers.
 *
 * @NL80211_ATTR_SCHED_SCAN_INTERVAL: Interval between scheduled scan
 *	cycles, in msecs.
 *
 * @NL80211_ATTR_SCHED_SCAN_MATCH: Nested attribute with one or more
 *	sets of attributes to match during scheduled scans.  Only BSSs
 *	that match any of the sets will be reported.  These are
 *	pass-thru filter rules.
 *	For a match to succeed, the BSS must match all attributes of a
 *	set.  Since not every hardware supports matching all types of
 *	attributes, there is no guarantee that the reported BSSs are
 *	fully complying with the match sets and userspace needs to be
 *	able to ignore them by itself.
 *	Thus, the implementation is somewhat hardware-dependent, but
 *	this is only an optimization and the userspace application
 *	needs to handle all the non-filtered results anyway.
 *	If the match attributes don't make sense when combined with
 *	the values passed in @NL80211_ATTR_SCAN_SSIDS (eg. if an SSID
 *	is included in the probe request, but the match attributes
 *	will never let it go through), -EINVAL may be returned.
 *	If ommited, no filtering is done.
 *
 * @NL80211_ATTR_INTERFACE_COMBINATIONS: Nested attribute listing the supported
 *	interface combinations. In each nested item, it contains attributes
 *	defined in &enum nl80211_if_combination_attrs.
 * @NL80211_ATTR_SOFTWARE_IFTYPES: Nested attribute (just like
 *	%NL80211_ATTR_SUPPORTED_IFTYPES) containing the interface types that
 *	are managed in software: interfaces of these types aren't subject to
 *	any restrictions in their number or combinations.
 *
 * @NL80211_ATTR_REKEY_DATA: nested attribute containing the information
 *	necessary for GTK rekeying in the device, see &enum nl80211_rekey_data.
 *
 * @NL80211_ATTR_SCAN_SUPP_RATES: rates per to be advertised as supported in scan,
 *	nested array attribute containing an entry for each band, with the entry
 *	being a list of supported rates as defined by IEEE 802.11 7.3.2.2 but
 *	without the length restriction (at most %NL80211_MAX_SUPP_RATES).
 *
 * @NL80211_ATTR_HIDDEN_SSID: indicates whether SSID is to be hidden from Beacon
 *	and Probe Response (when response to wildcard Probe Request); see
 *	&enum nl80211_hidden_ssid, represented as a u32
 *
 * @NL80211_ATTR_IE_PROBE_RESP: Information element(s) for Probe Response frame.
 *	This is used with %NL80211_CMD_NEW_BEACON and %NL80211_CMD_SET_BEACON to
 *	provide extra IEs (e.g., WPS/P2P IE) into Probe Response frames when the
 *	driver (or firmware) replies to Probe Request frames.
 * @NL80211_ATTR_IE_ASSOC_RESP: Information element(s) for (Re)Association
 *	Response frames. This is used with %NL80211_CMD_NEW_BEACON and
 *	%NL80211_CMD_SET_BEACON to provide extra IEs (e.g., WPS/P2P IE) into
 *	(Re)Association Response frames when the driver (or firmware) replies to
 *	(Re)Association Request frames.
 *
 * @NL80211_ATTR_STA_WME: Nested attribute containing the wme configuration
 *	of the station, see &enum nl80211_sta_wme_attr.
 * @NL80211_ATTR_SUPPORT_AP_UAPSD: the device supports uapsd when working
 *	as AP.
 *
 * @NL80211_ATTR_ROAM_SUPPORT: Indicates whether the firmware is capable of
 *	roaming to another AP in the same ESS if the signal lever is low.
 *
 * @NL80211_ATTR_PMKSA_CANDIDATE: Nested attribute containing the PMKSA caching
 *	candidate information, see &enum nl80211_pmksa_candidate_attr.
 *
 * @NL80211_ATTR_TX_NO_CCK_RATE: Indicates whether to use CCK rate or not
 *	for management frames transmission. In order to avoid p2p probe/action
 *	frames are being transmitted at CCK rate in 2GHz band, the user space
 *	applications use this attribute.
 *	This attribute is used with %NL80211_CMD_TRIGGER_SCAN and
 *	%NL80211_CMD_FRAME commands.
 *
 * @NL80211_ATTR_TDLS_ACTION: Low level TDLS action code (e.g. link setup
 *	request, link setup confirm, link teardown, etc.). Values are
 *	described in the TDLS (802.11z) specification.
 * @NL80211_ATTR_TDLS_DIALOG_TOKEN: Non-zero token for uniquely identifying a
 *	TDLS conversation between two devices.
 * @NL80211_ATTR_TDLS_OPERATION: High level TDLS operation; see
 *	&enum nl80211_tdls_operation, represented as a u8.
 * @NL80211_ATTR_TDLS_SUPPORT: A flag indicating the device can operate
 *	as a TDLS peer sta.
 * @NL80211_ATTR_TDLS_EXTERNAL_SETUP: The TDLS discovery/setup and teardown
 *	procedures should be performed by sending TDLS packets via
 *	%NL80211_CMD_TDLS_MGMT. Otherwise %NL80211_CMD_TDLS_OPER should be
 *	used for asking the driver to perform a TDLS operation.
 *
 * @NL80211_ATTR_DEVICE_AP_SME: This u32 attribute may be listed for devices
 *	that have AP support to indicate that they have the AP SME integrated
 *	with support for the features listed in this attribute, see
 *	&enum nl80211_ap_sme_features.
 *
 * @NL80211_ATTR_DONT_WAIT_FOR_ACK: Used with %NL80211_CMD_FRAME, this tells
 *	the driver to not wait for an acknowledgement. Note that due to this,
 *	it will also not give a status callback nor return a cookie. This is
 *	mostly useful for probe responses to save airtime.
 *
 * @NL80211_ATTR_FEATURE_FLAGS: This u32 attribute contains flags from
 *	&enum nl80211_feature_flags and is advertised in wiphy information.
 * @NL80211_ATTR_PROBE_RESP_OFFLOAD: Indicates that the HW responds to probe
 *	requests while operating in AP-mode.
 *	This attribute holds a bitmap of the supported protocols for
 *	offloading (see &enum nl80211_probe_resp_offload_support_attr).
 *
 * @NL80211_ATTR_PROBE_RESP: Probe Response template data. Contains the entire
 *	probe-response frame. The DA field in the 802.11 header is zero-ed out,
 *	to be filled by the FW.
 * @NL80211_ATTR_DISABLE_HT:  Force HT capable interfaces to disable
 *      this feature.  Currently, only supported in mac80211 drivers.
 * @NL80211_ATTR_HT_CAPABILITY_MASK: Specify which bits of the
 *      ATTR_HT_CAPABILITY to which attention should be paid.
 *      Currently, only mac80211 NICs support this feature.
 *      The values that may be configured are:
 *       MCS rates, MAX-AMSDU, HT-20-40 and HT_CAP_SGI_40
 *       AMPDU density and AMPDU factor.
 *      All values are treated as suggestions and may be ignored
 *      by the driver as required.  The actual values may be seen in
 *      the station debugfs ht_caps file.
 *
 * @NL80211_ATTR_DFS_REGION: region for regulatory rules which this country
 *    abides to when initiating radiation on DFS channels. A country maps
 *    to one DFS region.
 *
 * @NL80211_ATTR_NOACK_MAP: This u16 bitmap contains the No Ack Policy of
 *      up to 16 TIDs.
 *
 * @NL80211_ATTR_INACTIVITY_TIMEOUT: timeout value in seconds, this can be
 *	used by the drivers which has MLME in firmware and does not have support
 *	to report per station tx/rx activity to free up the staion entry from
 *	the list. This needs to be used when the driver advertises the
 *	capability to timeout the stations.
 *
 * @NL80211_ATTR_RX_SIGNAL_DBM: signal strength in dBm (as a 32-bit int);
 *	this attribute is (depending on the driver capabilities) added to
 *	received frames indicated with %NL80211_CMD_FRAME.
 *
 * @NL80211_ATTR_BG_SCAN_PERIOD: Background scan period in seconds
 *      or 0 to disable background scan.
 *
 * @NL80211_ATTR_USER_REG_HINT_TYPE: type of regulatory hint passed from
 *	userspace. If unset it is assumed the hint comes directly from
 *	a user. If set code could specify exactly what type of source
 *	was used to provide the hint. For the different types of
 *	allowed user regulatory hints see nl80211_user_reg_hint_type.
 *
 * @NL80211_ATTR_CONN_FAILED_REASON: The reason for which AP has rejected
 *	the connection request from a station. nl80211_connect_failed_reason
 *	enum has different reasons of connection failure.
 *
 * @NL80211_ATTR_SAE_DATA: SAE elements in Authentication frames. This starts
 *	with the Authentication transaction sequence number field.
 *
 * @NL80211_ATTR_VHT_CAPABILITY: VHT Capability information element (from
 *	association request when used with NL80211_CMD_NEW_STATION)
 *
 * @NL80211_ATTR_SCAN_FLAGS: scan request control flags (u32)
 *
 * @NL80211_ATTR_P2P_CTWINDOW: P2P GO Client Traffic Window (u8), used with
 *	the START_AP and SET_BSS commands
 * @NL80211_ATTR_P2P_OPPPS: P2P GO opportunistic PS (u8), used with the
 *	START_AP and SET_BSS commands. This can have the values 0 or 1;
 *	if not given in START_AP 0 is assumed, if not given in SET_BSS
 *	no change is made.
 *
 * @NL80211_ATTR_LOCAL_MESH_POWER_MODE: local mesh STA link-specific power mode
 *	defined in &enum nl80211_mesh_power_mode.
 *
 * @NL80211_ATTR_ACL_POLICY: ACL policy, see &enum nl80211_acl_policy,
 *	carried in a u32 attribute
 *
 * @NL80211_ATTR_MAC_ADDRS: Array of nested MAC addresses, used for
 *	MAC ACL.
 *
 * @NL80211_ATTR_MAC_ACL_MAX: u32 attribute to advertise the maximum
 *	number of MAC addresses that a device can support for MAC
 *	ACL.
 *
 * @NL80211_ATTR_RADAR_EVENT: Type of radar event for notification to userspace,
 *	contains a value of enum nl80211_radar_event (u32).
 *
 * @NL80211_ATTR_EXT_CAPA: 802.11 extended capabilities that the kernel driver
 *	has and handles. The format is the same as the IE contents. See
 *	802.11-2012 8.4.2.29 for more information.
 * @NL80211_ATTR_EXT_CAPA_MASK: Extended capabilities that the kernel driver
 *	has set in the %NL80211_ATTR_EXT_CAPA value, for multibit fields.
 *
 * @NL80211_ATTR_STA_CAPABILITY: Station capabilities (u16) are advertised to
 *	the driver, e.g., to enable TDLS power save (PU-APSD).
 *
 * @NL80211_ATTR_STA_EXT_CAPABILITY: Station extended capabilities are
 *	advertised to the driver, e.g., to enable TDLS off channel operations
 *	and PU-APSD.
 *
 * @NL80211_ATTR_PROTOCOL_FEATURES: global nl80211 feature flags, see
 *	&enum nl80211_protocol_features, the attribute is a u32.
 *
 * @NL80211_ATTR_SPLIT_WIPHY_DUMP: flag attribute, userspace supports
 *	receiving the data for a single wiphy split across multiple
 *	messages, given with wiphy dump message
 *
 * @NL80211_ATTR_MDID: Mobility Domain Identifier
 *
 * @NL80211_ATTR_IE_RIC: Resource Information Container Information
 *	Element
 *
 * @NL80211_ATTR_CRIT_PROT_ID: critical protocol identifier requiring increased
 *	reliability, see &enum nl80211_crit_proto_id (u16).
 * @NL80211_ATTR_MAX_CRIT_PROT_DURATION: duration in milliseconds in which
 *      the connection should have increased reliability (u16).
 *
 * @NL80211_ATTR_PEER_AID: Association ID for the peer TDLS station (u16).
 *	This is similar to @NL80211_ATTR_STA_AID but with a difference of being
 *	allowed to be used with the first @NL80211_CMD_SET_STATION command to
 *	update a TDLS peer STA entry.
 *
 * @NL80211_ATTR_COALESCE_RULE: Coalesce rule information.
 *
 * @NL80211_ATTR_CH_SWITCH_COUNT: u32 attribute specifying the number of TBTT's
 *	until the channel switch event.
 * @NL80211_ATTR_CH_SWITCH_BLOCK_TX: flag attribute specifying that transmission
 *	must be blocked on the current channel (before the channel switch
 *	operation).
 * @NL80211_ATTR_CSA_IES: Nested set of attributes containing the IE information
 *	for the time while performing a channel switch.
 * @NL80211_ATTR_CSA_C_OFF_BEACON: Offset of the channel switch counter
 *	field in the beacons tail (%NL80211_ATTR_BEACON_TAIL).
 * @NL80211_ATTR_CSA_C_OFF_PRESP: Offset of the channel switch counter
 *	field in the probe response (%NL80211_ATTR_PROBE_RESP).
 *
 * @NL80211_ATTR_RXMGMT_FLAGS: flags for nl80211_send_mgmt(), u32.
 *	As specified in the &enum nl80211_rxmgmt_flags.
 *
 * @NL80211_ATTR_STA_SUPPORTED_CHANNELS: array of supported channels.
 *
 * @NL80211_ATTR_STA_SUPPORTED_OPER_CLASSES: array of supported
 *      supported operating classes.
 *
 * @NL80211_ATTR_HANDLE_DFS: A flag indicating whether user space
 *	controls DFS operation in IBSS mode. If the flag is included in
 *	%NL80211_CMD_JOIN_IBSS request, the driver will allow use of DFS
 *	channels and reports radar events to userspace. Userspace is required
 *	to react to radar events, e.g. initiate a channel switch or leave the
 *	IBSS network.
 *
 * @NL80211_ATTR_MAX: highest attribute number currently defined
 * @__NL80211_ATTR_AFTER_LAST: internal use
 */
"""

# don't change the order or add anything between, this is ABI!
NL80211_ATTR_UNSPEC                         =   0
NL80211_ATTR_WIPHY                          =   1
NL80211_ATTR_WIPHY_NAME                     =   2
NL80211_ATTR_IFINDEX                        =   3
NL80211_ATTR_IFNAME                         =   4
NL80211_ATTR_IFTYPE                         =   5
NL80211_ATTR_MAC                            =   6
NL80211_ATTR_KEY_DATA                       =   7
NL80211_ATTR_KEY_IDX                        =   8
NL80211_ATTR_KEY_CIPHER                     =   9
NL80211_ATTR_KEY_SEQ                        =  10
NL80211_ATTR_KEY_DEFAULT                    =  11
NL80211_ATTR_BEACON_INTERVAL                =  12
NL80211_ATTR_DTIM_PERIOD                    =  13
NL80211_ATTR_BEACON_HEAD                    =  14
NL80211_ATTR_BEACON_TAIL                    =  15
NL80211_ATTR_STA_AID                        =  16
NL80211_ATTR_STA_FLAGS                      =  17
NL80211_ATTR_STA_LISTEN_INTERVAL            =  18
NL80211_ATTR_STA_SUPPORTED_RATES            =  19
NL80211_ATTR_STA_VLAN                       =  20
NL80211_ATTR_STA_INFO                       =  21
NL80211_ATTR_WIPHY_BANDS                    =  22
NL80211_ATTR_MNTR_FLAGS                     =  23
NL80211_ATTR_MESH_ID                        =  24
NL80211_ATTR_STA_PLINK_ACTION               =  25
NL80211_ATTR_MPATH_NEXT_HOP                 =  26
NL80211_ATTR_MPATH_INFO                     =  27
NL80211_ATTR_BSS_CTS_PROT                   =  28
NL80211_ATTR_BSS_SHORT_PREAMBLE             =  29
NL80211_ATTR_BSS_SHORT_SLOT_TIME            =  30
NL80211_ATTR_HT_CAPABILITY                  =  31
NL80211_ATTR_SUPPORTED_IFTYPES              =  32
NL80211_ATTR_REG_ALPHA2                     =  33
NL80211_ATTR_REG_RULES                      =  34
NL80211_ATTR_MESH_CONFIG                    =  35
NL80211_ATTR_BSS_BASIC_RATES                =  36
NL80211_ATTR_WIPHY_TXQ_PARAMS               =  37
NL80211_ATTR_WIPHY_FREQ                     =  38
NL80211_ATTR_WIPHY_CHANNEL_TYPE             =  38
NL80211_ATTR_KEY_DEFAULT_MGMT               =  39
NL80211_ATTR_MGMT_SUBTYPE                   =  40
NL80211_ATTR_IE                             =  41
NL80211_ATTR_MAX_NUM_SCAN_SSIDS             =  42
NL80211_ATTR_SCAN_FREQUENCIES               =  43
NL80211_ATTR_SCAN_SSIDS                     =  44
NL80211_ATTR_GENERATION                     =  45 # replaces old SCAN_GENERATION
NL80211_ATTR_BSS                            =  46
NL80211_ATTR_REG_INITIATOR                  =  47
NL80211_ATTR_REG_TYPE                       =  48
NL80211_ATTR_SUPPORTED_COMMANDS             =  49
NL80211_ATTR_FRAME                          =  50
NL80211_ATTR_SSID                           =  51
NL80211_ATTR_AUTH_TYPE                      =  52
NL80211_ATTR_REASON_CODE                    =  53
NL80211_ATTR_KEY_TYPE                       =  54
NL80211_ATTR_MAX_SCAN_IE_LEN                =  55
NL80211_ATTR_CIPHER_SUITES                  =  56
NL80211_ATTR_FREQ_BEFORE                    =  57
NL80211_ATTR_FREQ_AFTER                     =  58
NL80211_ATTR_FREQ_FIXED                     =  59
NL80211_ATTR_WIPHY_RETRY_SHORT              =  60
NL80211_ATTR_WIPHY_RETRY_LONG               =  61
NL80211_ATTR_WIPHY_FRAG_THRESHOLD           =  62
NL80211_ATTR_WIPHY_RTS_THRESHOLD            =  63
NL80211_ATTR_TIMED_OUT                      =  64
NL80211_ATTR_USE_MFP                        =  65
NL80211_ATTR_STA_FLAGS2                     =  66
NL80211_ATTR_CONTROL_PORT                   =  67
NL80211_ATTR_TESTDATA                       =  68
NL80211_ATTR_PRIVACY                        =  69
NL80211_ATTR_DISCONNECTED_BY_AP             =  70
NL80211_ATTR_STATUS_CODE                    =  71
NL80211_ATTR_CIPHER_SUITES_PAIRWISE         =  72
NL80211_ATTR_CIPHER_SUITE_GROUP             =  73
NL80211_ATTR_WPA_VERSIONS                   =  74
NL80211_ATTR_AKM_SUITES                     =  75
NL80211_ATTR_REQ_IE                         =  76
NL80211_ATTR_RESP_IE                        =  77
NL80211_ATTR_PREV_BSSID                     =  78
NL80211_ATTR_KEY                            =  79
NL80211_ATTR_KEYS                           =  80
NL80211_ATTR_PID                            =  81
NL80211_ATTR_4ADDR                          =  82
NL80211_ATTR_SURVEY_INFO                    =  83
NL80211_ATTR_PMKID                          =  84
NL80211_ATTR_MAX_NUM_PMKIDS                 =  85
NL80211_ATTR_DURATION                       =  86
NL80211_ATTR_COOKIE                         =  87
NL80211_ATTR_WIPHY_COVERAGE_CLASS           =  88
NL80211_ATTR_TX_RATES                       =  89
NL80211_ATTR_FRAME_MATCH                    =  90
NL80211_ATTR_ACK                            =  91
NL80211_ATTR_PS_STATE                       =  92
NL80211_ATTR_CQM                            =  93
NL80211_ATTR_LOCAL_STATE_CHANGE             =  94
NL80211_ATTR_AP_ISOLATE                     =  95
NL80211_ATTR_WIPHY_TX_POWER_SETTING         =  96
NL80211_ATTR_WIPHY_TX_POWER_LEVEL           =  97
NL80211_ATTR_TX_FRAME_TYPES                 =  98
NL80211_ATTR_RX_FRAME_TYPES                 =  99
NL80211_ATTR_FRAME_TYPE                     = 100
NL80211_ATTR_CONTROL_PORT_ETHERTYPE         = 101
NL80211_ATTR_CONTROL_PORT_NO_ENCRYPT        = 102
NL80211_ATTR_SUPPORT_IBSS_RSN               = 103
NL80211_ATTR_WIPHY_ANTENNA_TX               = 104
NL80211_ATTR_WIPHY_ANTENNA_RX               = 105
NL80211_ATTR_MCAST_RATE                     = 106
NL80211_ATTR_OFFCHANNEL_TX_OK               = 107
NL80211_ATTR_BSS_HT_OPMODE                  = 108
NL80211_ATTR_KEY_DEFAULT_TYPES              = 109
NL80211_ATTR_MAX_REMAIN_ON_CHANNEL_DURATION = 110
NL80211_ATTR_MESH_SETUP                     = 111
NL80211_ATTR_WIPHY_ANTENNA_AVAIL_TX         = 112
NL80211_ATTR_WIPHY_ANTENNA_AVAIL_RX         = 113
NL80211_ATTR_SUPPORT_MESH_AUTH              = 114
NL80211_ATTR_STA_PLINK_STATE                = 115
NL80211_ATTR_WOWLAN_TRIGGERS                = 116
NL80211_ATTR_WOWLAN_TRIGGERS_SUPPORTED      = 117
NL80211_ATTR_SCHED_SCAN_INTERVAL            = 118
NL80211_ATTR_INTERFACE_COMBINATIONS         = 119
NL80211_ATTR_SOFTWARE_IFTYPES               = 120
NL80211_ATTR_REKEY_DATA                     = 121
NL80211_ATTR_MAX_NUM_SCHED_SCAN_SSIDS       = 122
NL80211_ATTR_MAX_SCHED_SCAN_IE_LEN          = 123
NL80211_ATTR_SCAN_SUPP_RATES                = 124
NL80211_ATTR_HIDDEN_SSID                    = 125
NL80211_ATTR_IE_PROBE_RESP                  = 126
NL80211_ATTR_IE_ASSOC_RESP                  = 127
NL80211_ATTR_STA_WME                        = 128
NL80211_ATTR_SUPPORT_AP_UAPSD               = 129
NL80211_ATTR_ROAM_SUPPORT                   = 130
NL80211_ATTR_SCHED_SCAN_MATCH               = 131
NL80211_ATTR_MAX_MATCH_SETS                 = 132
NL80211_ATTR_PMKSA_CANDIDATE                = 133
NL80211_ATTR_TX_NO_CCK_RATE                 = 134
NL80211_ATTR_TDLS_ACTION                    = 135
NL80211_ATTR_TDLS_DIALOG_TOKEN              = 136
NL80211_ATTR_TDLS_OPERATION                 = 137
NL80211_ATTR_TDLS_SUPPORT                   = 138
NL80211_ATTR_TDLS_EXTERNAL_SETUP            = 139
NL80211_ATTR_DEVICE_AP_SME                  = 140
NL80211_ATTR_DONT_WAIT_FOR_ACK              = 141
NL80211_ATTR_FEATURE_FLAGS                  = 142
NL80211_ATTR_PROBE_RESP_OFFLOAD             = 143
NL80211_ATTR_PROBE_RESP                     = 145
NL80211_ATTR_DFS_REGION                     = 146
NL80211_ATTR_DISABLE_HT                     = 147
NL80211_ATTR_HT_CAPABILITY_MASK             = 148
NL80211_ATTR_NOACK_MAP                      = 149
NL80211_ATTR_INACTIVITY_TIMEOUT             = 150
NL80211_ATTR_RX_SIGNAL_DBM                  = 151
NL80211_ATTR_BG_SCAN_PERIOD                 = 152
NL80211_ATTR_WDEV                           = 153
NL80211_ATTR_USER_REG_HINT_TYPE             = 154
NL80211_ATTR_CONN_FAILED_REASON             = 155
NL80211_ATTR_SAE_DATA                       = 156
NL80211_ATTR_VHT_CAPABILITY                 = 157
NL80211_ATTR_SCAN_FLAGS                     = 158
NL80211_ATTR_CHANNEL_WIDTH                  = 159
NL80211_ATTR_CENTER_FREQ1                   = 160
NL80211_ATTR_CENTER_FREQ2                   = 161
NL80211_ATTR_P2P_CTWINDOW                   = 162
NL80211_ATTR_P2P_OPPPS                      = 163
NL80211_ATTR_LOCAL_MESH_POWER_MODE          = 164
NL80211_ATTR_ACL_POLICY                     = 165
NL80211_ATTR_MAC_ADDRS                      = 166
NL80211_ATTR_MAC_ACL_MAX                    = 167
NL80211_ATTR_RADAR_EVENT                    = 168
NL80211_ATTR_EXT_CAPA                       = 169
NL80211_ATTR_EXT_CAPA_MASK                  = 170
NL80211_ATTR_STA_CAPABILITY                 = 171
NL80211_ATTR_STA_EXT_CAPABILITY             = 172
NL80211_ATTR_PROTOCOL_FEATURES              = 173
NL80211_ATTR_SPLIT_WIPHY_DUMP               = 174
NL80211_ATTR_DISABLE_VHT                    = 175
NL80211_ATTR_VHT_CAPABILITY_MASK            = 176
NL80211_ATTR_MDID                           = 177
NL80211_ATTR_IE_RIC                         = 178
NL80211_ATTR_CRIT_PROT_ID                   = 179
NL80211_ATTR_MAX_CRIT_PROT_DURATION         = 180
NL80211_ATTR_PEER_AID                       = 181
NL80211_ATTR_COALESCE_RULE                  = 182
NL80211_ATTR_CH_SWITCH_COUNT                = 183
NL80211_ATTR_CH_SWITCH_BLOCK_TX             = 184
NL80211_ATTR_CSA_IES                        = 185
NL80211_ATTR_CSA_C_OFF_BEACON               = 186
NL80211_ATTR_CSA_C_OFF_PRESP                = 187
NL80211_ATTR_RXMGMT_FLAGS                   = 188
NL80211_ATTR_STA_SUPPORTED_CHANNELS         = 189
NL80211_ATTR_STA_SUPPORTED_OPER_CLASSES     = 190
NL80211_ATTR_HANDLE_DFS                     = 191
# add attributes here, update the policy in nl80211.c
__NL80211_ATTR_AFTER_LAST                   = 192
NL80211_ATTR_MAX = __NL80211_ATTR_AFTER_LAST - 1


# source-level API compatibility
NL80211_ATTR_SCAN_GENERATION = NL80211_ATTR_GENERATION
NL80211_ATTR_MESH_PARAMS     = NL80211_ATTR_MESH_CONFIG

# Allow user space programs to use #ifdef on new attributes by defining them here
NL80211_CMD_CONNECT                 = NL80211_CMD_CONNECT
NL80211_ATTR_HT_CAPABILITY          = NL80211_ATTR_HT_CAPABILITY
NL80211_ATTR_BSS_BASIC_RATES        = NL80211_ATTR_BSS_BASIC_RATES
NL80211_ATTR_WIPHY_TXQ_PARAMS       = NL80211_ATTR_WIPHY_TXQ_PARAMS
NL80211_ATTR_WIPHY_FREQ             = NL80211_ATTR_WIPHY_FREQ
NL80211_ATTR_WIPHY_CHANNEL_TYPE     = NL80211_ATTR_WIPHY_CHANNEL_TYPE
NL80211_ATTR_MGMT_SUBTYPE           = NL80211_ATTR_MGMT_SUBTYPE
NL80211_ATTR_IE                     = NL80211_ATTR_IE
NL80211_ATTR_REG_INITIATOR          = NL80211_ATTR_REG_INITIATOR
NL80211_ATTR_REG_TYPE               = NL80211_ATTR_REG_TYPE
NL80211_ATTR_FRAME                  = NL80211_ATTR_FRAME
NL80211_ATTR_SSID                   = NL80211_ATTR_SSID
NL80211_ATTR_AUTH_TYPE              = NL80211_ATTR_AUTH_TYPE
NL80211_ATTR_REASON_CODE            = NL80211_ATTR_REASON_CODE
NL80211_ATTR_CIPHER_SUITES_PAIRWISE = NL80211_ATTR_CIPHER_SUITES_PAIRWISE
NL80211_ATTR_CIPHER_SUITE_GROUP     = NL80211_ATTR_CIPHER_SUITE_GROUP
NL80211_ATTR_WPA_VERSIONS           = NL80211_ATTR_WPA_VERSIONS
NL80211_ATTR_AKM_SUITES             = NL80211_ATTR_AKM_SUITES
NL80211_ATTR_KEY                    = NL80211_ATTR_KEY
NL80211_ATTR_KEYS                   = NL80211_ATTR_KEYS
NL80211_ATTR_FEATURE_FLAGS          = NL80211_ATTR_FEATURE_FLAGS
