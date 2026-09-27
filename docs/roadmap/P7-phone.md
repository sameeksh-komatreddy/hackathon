# P7 Phone camera (needed for launch)

Design: the phone opens the same site at `/phone` and sends its camera to the computer as a **WebRTC video track**, peer to peer and encrypted. The computer treats that stream like any other webcam, so the existing tracker handles it unchanged, and it works on phones too slow to run the tracking models themselves. Video never passes through a server. The only server involved is a small signalling service that introduces the two devices.

## S17 ★ Signalling and pairing
- Cloudflare Worker (free tier) in `signal/`, deployed with `wrangler`. One room per pairing code, using a Durable Object (available on the free plan; confirm before building). The desktop and phone exchange the WebRTC offer, answer and ICE candidates through it, then disconnect.
- The pairing code is a random 128-bit value that expires after 10 minutes or its first use. Rate-limit each IP address. Store nothing after pairing.
- Record tab: QR code (the `qrcode` npm package) for `https://<site>/phone#code=…`, plus a "New code" button. Putting the code after `#` keeps it out of server logs.
- **Done when:** two browser tabs complete the offer/answer exchange through the deployed Worker.

## S18 Phone page and camera slot
- `/phone` page: port the user interface from `phone_camera.html` (start/stop, front/back camera switch, keep the screen awake, resume when the page is visible again). Replace the frame uploads with `RTCPeerConnection.addTrack`, capped at 640 px and 15 fps.
- Desktop: the incoming stream becomes a "Phone" option in the S07 camera picker. Show its connection status.
- **Done when:** a phone on the same Wi-Fi fills the side slot and a recorded session includes neck and torso angles.

## S19 ★ Connections across real networks
- STUN: a free public server (for example Google's). Without TURN, strict networks (school or work Wi-Fi, some mobile carriers) can block the connection. Check whether Cloudflare's TURN service still has a free tier; if so, use it, with short-lived credentials issued by the Worker.
- Clear errors for each failure point (code expired, peer not found, ICE failed) with the hotspot tip, reconnect automatically after drops, and tidy up when the tab closes.
- Test matrix: same Wi-Fi, phone on mobile data, phone hotspot, a school or guest Wi-Fi, iPhone Safari, Android Chrome. Record the results here.
- **Done when:** the matrix is filled in and every failure shows a useful message.

## Results
_(fill in)_
