**This file was made without AI**


# LoRa Module information

### Rationale:
As a part of the cyberdeck, a LoRa Module was an  choice given the hobby in amateur radio and is a useful utility in the *'off-grid'* style of the cyber-deck. the LoRa (Long Range Radio) module will enable the use of mesh networks which are popular in major population centers like Meshtastic (meshtastic.org), Meshcore (meshcore.io) and other open-source 915Mhz (ISM BAND) uses.

*note: the 915Mhz ISM band is allowed to be used by everyone license free*

### Spec
The module used is the Heltec V3 Module which I personally already had available. However, as the LoRa module is stand alone, it would be okay to use any module.

### Considerations
#### 1. RF Overload
   The idea of having a radio transmitter adjacent to both an SDR receiver and a GPS antenna there needs to be some consideration as to the front end overload of the receivers. after consulting **AI** the apparent answer is that the TX power of the Heltec V3 (~20dBm) is unlikely to impact the front end of either the receivers. However, recieve may be impacted while active, especially if the module is just set to the 'client' setting (as opposed to options like 'client mute') may transmit without prompt to relay messages to the mesh. For this reason, the LoRa module needs to have a separate power line as it can be switched off as required.

#### 2. Connection
   The Heltec V3 module needs to connect to a companion device to enable it to message. Weather it is the *built in mini computer for the SDR* (planned at this stage) or a mobile phone. at the time    of writing I'm considering adding a networking element to the board which will possible broadcast wifi/Ethernet 

#### 3. Antenna - Taken from main README
This is a wider problem with the cyberdeck, the antennas are an issue with the enclosure being a pelican case. Not really wanting to compromise the IP rating, the antennas will likely need to stay inside the case, possibly as a flip out element off the side of the deck to allow for full use of computer. 
