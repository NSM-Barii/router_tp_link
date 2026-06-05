#!/bin/bash
# UPNP ENUMERATION
# TARGET: TP-Link Archer AX1450 — MiniUPnP on port 1900

TARGET="192.168.0.1:1900"
OUT="$(dirname "$0")"

echo "[*] Fetching SCPD files..."
curl -s "http://$TARGET/cqcos/WANIPCn.xml" > "$OUT/upnp_WANIPCn.xml"
curl -s "http://$TARGET/cqcos/WANCfg.xml"  > "$OUT/upnp_WANCfg.xml"
curl -s "http://$TARGET/cqcos/L3F.xml"     > "$OUT/upnp_L3F.xml"
echo "[+] Saved WANIPCn.xml, WANCfg.xml, L3F.xml"

echo ""
echo "[*] GetExternalIPAddress..."
curl -s -X POST "http://$TARGET/cqcos/ctl/IPConn" \
  -H 'Content-Type: text/xml' \
  -H 'SOAPAction: "urn:schemas-upnp-org:service:WANIPConnection:1#GetExternalIPAddress"' \
  -d '<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body><u:GetExternalIPAddress xmlns:u="urn:schemas-upnp-org:service:WANIPConnection:1"></u:GetExternalIPAddress></s:Body></s:Envelope>' \
  | tee "$OUT/upnp_GetExternalIP.txt"

echo ""
echo "[*] GetStatusInfo..."
curl -s -X POST "http://$TARGET/cqcos/ctl/IPConn" \
  -H 'Content-Type: text/xml' \
  -H 'SOAPAction: "urn:schemas-upnp-org:service:WANIPConnection:1#GetStatusInfo"' \
  -d '<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body><u:GetStatusInfo xmlns:u="urn:schemas-upnp-org:service:WANIPConnection:1"></u:GetStatusInfo></s:Body></s:Envelope>' \
  | tee "$OUT/upnp_GetStatusInfo.txt"

echo ""
echo "[*] GetNATRSIPStatus..."
curl -s -X POST "http://$TARGET/cqcos/ctl/IPConn" \
  -H 'Content-Type: text/xml' \
  -H 'SOAPAction: "urn:schemas-upnp-org:service:WANIPConnection:1#GetNATRSIPStatus"' \
  -d '<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body><u:GetNATRSIPStatus xmlns:u="urn:schemas-upnp-org:service:WANIPConnection:1"></u:GetNATRSIPStatus></s:Body></s:Envelope>' \
  | tee "$OUT/upnp_GetNATRSIP.txt"

echo ""
echo "[*] GetPortMappingNumberOfEntries..."
curl -s -X POST "http://$TARGET/cqcos/ctl/IPConn" \
  -H 'Content-Type: text/xml' \
  -H 'SOAPAction: "urn:schemas-upnp-org:service:WANIPConnection:1#GetPortMappingNumberOfEntries"' \
  -d '<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body><u:GetPortMappingNumberOfEntries xmlns:u="urn:schemas-upnp-org:service:WANIPConnection:1"></u:GetPortMappingNumberOfEntries></s:Body></s:Envelope>' \
  | tee "$OUT/upnp_PortMappingCount.txt"

echo ""
echo "[*] GetDefaultConnectionService (L3F)..."
curl -s -X POST "http://$TARGET/cqcos/ctl/L3F" \
  -H 'Content-Type: text/xml' \
  -H 'SOAPAction: "urn:schemas-upnp-org:service:Layer3Forwarding:1#GetDefaultConnectionService"' \
  -d '<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body><u:GetDefaultConnectionService xmlns:u="urn:schemas-upnp-org:service:Layer3Forwarding:1"></u:GetDefaultConnectionService></s:Body></s:Envelope>' \
  | tee "$OUT/upnp_L3F_DefaultConn.txt"

echo ""
echo "[+] Done. Results saved to $OUT"
