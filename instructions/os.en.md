# <a id="os"/>Operating Systems

We have successfully infiltrated the greenery's network, and have installed file crawlers on their systems that will send their files to us. Your mission is to write a server that will receive the data and write it to our own systems. With this, we can find out their next moves!

We've found that the greenery's network is somewhat unreliable, so you may experience packet loss, out-of-order packets, and bit flips.

You may use any programming language to complete your task. We have provided you with the source code for a test crawler (`crawler.py`). You may refer to its implementation.

\* For simplicity, examples do not include parity bits, and assume that network and host byte orders are both big endian.

## <a id="requests"/>Crawler Requests

**Crawlers will send all transmissions on port `7331`.**

**Integral values are sent in network byte order (see `man htonl` for details).**

Each request starts with a 10-byte header:
* 2 bytes: Magic number 0xC505
* 2 bytes: Total packet size, including header
* 2 bytes: Crawler identifier
* 4 bytes: Command name in ASCII

Payload size is obtained via `size - sizeof(header)`. Packets in this protocol are a maximum of 508 bytes, which means that a payload will be at most 498 bytes long.

### <a id="upld"/>UPLD

This is the first packet a crawler will send. It signals the start of a file upload. It contains the crawler's identifier in the header, and the full path of the file in the payload (no null terminator).

```
[0x00000000]    C5 05 00 1B 00 01 55 50  4C 44 2F 76 61 72 2F 6C    |......UPLD/var/l|
[0x00000010]    6F 67 2F 61 75 74 68 2E  6C 6F 67                   |og/auth.log|
```

\* Duplicate files may be accepted in case the files differ.

### <a id="mode"/>MODE

This packet is not required. If sent, it will precede all DATA packets. It contains information on how the file will be transferred. If this packet is not sent, ['block'](#block) mode is assumed. See [here](#modes) for details.

```
[0x00000000]    C5 05 00 0F 00 01 4D 4F  44 45 62 6C 6F 63 6B       |......MODEblock|
```

### <a id="seqn"/>SEQN

This packet is not required. If sent, it will precede all DATA packets. It contains the initial sequence number for the transfer. If not sent, 0 is assumed.

Here's an example with number 0x1111:

```
[0x00000000]    C5 05 00 08 00 01 53 45  51 4E 11 11                |......SEQN..|
```

### <a id="data"/>DATA

This type of packet will be sent until the file transfer is complete. The first 2 bytes of the payload are the upload id. The next 2 bytes are the sequence number. Uploads are terminated with an empty DATA packet (the sequence number and upload id are still present). The following packet has sequence number 8039 with id 128:

```
[0x00000000]    C5 05 02 2F 00 01 44 41  54 41 00 80 1F 67 25 50    |.../....DATA.g%P|
[0x00000010]    44 46 2D 31 2E 36 0D 25  E2 E3 CF D3 0D 0A 32 39    |DF-1.6.%......29|
[0x00000020]    ...
```

## <a id="responses"/>Server Response

The server should send a response to the crawler in the following cases:
- When a new upload is requested (`UPLD` packet)
- WHen an upload is completed (empty `DATA` packet)
- When upload metadata is received (`SEQN` or `MODE` packets)
- Upon detecting packet loss
- On error

### <a id='upld_received'>Upload Request Received

When the server receives a new upload request, it should acknowledge it with the string 'UPLOADING', followed by a 2-byte id for the upload. The crawler will keep sending an `UPLD` packet until it receives this response. The following example returns id 8039:

```
[0x00000000]    55 50 4C 4F 41 44 49 4E  47 1F 67                   |UPLOADING.g|
```

### <a id="upld_end">Upload Completed

When the server receives an empty `DATA` packet, it should respond with 'UPLOAD END' followed by the file path sent in the initial upload request.

```
[0x00000000]    55 50 4C 4F 41 44 20 45  42 44 2F 76 61 72 2F 6C    |......UPLD/var/l|
[0x00000010]    6F 67 2F 61 75 74 68 2E  6C 6F 67                   |og/auth.log|
```

### <a id='meta_received'>Metadata Received

When the server receives a metadata packet, it should acknowledge it with the string 'METADATA' followed by the packet type. The crawler will keep sending the metadata packet until it receives confirmation with the appropriate response packet.

`SEQN` response:

```
[0x00000000]    4D 45 54 41 44 41 54 41  53 45 51 4E                |METADATASEQN|
```

`MODE` response:

```
[0x00000000]    4D 45 54 41 44 41 54 41  4D 4F 44 45                |METADATAMODE|
```

### <a id="loss"/>Packet Loss

To report packet loss, the server should reply with the string 'LOSS', the number of missed packets, followed by a list of sequence numbers. For example, to report the loss of packets 2, 3, and 16 (ie the server received packets 1, 4 through 15, and a sequence number greater than 16), the server should send the following packet:

```
[0x00000000]    4C 4F 53 53 00 03 00 02  00 03 00 10                |LOSS........|
```

NB: The number of missed packets is 2 bytes long, and so is each sequence number.

The server can choose to report every time a packet is missed, or send larger lists. Upon an EOF DATA packet, the crawler will keep listening for some time before closing its socket.

### <a id="errors"/>Errors

This response tells the client that an error occurred while processing the previous request. The payload is the string 'IAMERR', followed by 2 bytes indicating the total packet length, followed by an error message. This is for server exceptions, invalid packets, or any case not covered by the other responses.

The following error packet has the message "fail":

```
[0x00000000]    49 41 4D 45 52 52 00 0C  66 61 69 6C                |IAMERR..fail|
```

## <a id="modes"/>Modes

### <a id="block"/>Block

This is the default mode. The crawler will send as many packets as necessary to fully upload the file. The crawler will split the file into chunks and send them one by one, followed by an empty DATA packet to indicate EOF.

To use this mode, the crawler will send a MODE packet with the string 'block' or no MODE packet at all.

```
[0x00000000]    C5 05 00 0F 00 01 4D 4F  44 45 62 6C 6F 63 6B       |......MODEblock|
```

### <a id="compressed"/>Compressed

This mode is similar to 'block' mode, but the data in the packet will be run-length encoded (RLE). The [parity bits](#parity) are computed and added _after_ the data is encoded. Parity bits can be disabled during development using [environment variables](#helpme).

To use this mode, the crawler will send a MODE packet with the string 'compressed'.

```
[0x00000000]    C5 05 00 14 00 01 4D 4F  44 45 63 6F 6D 70 72 65    |......MODEcompre|
[0x00000010]    73 73 65 64                                         |ssed|
```

RLE is a form of lossless data compression in which runs (a run is sequence of consecutive values that are the same) of data are stored as a single count and data value. Consider black text on a solid white background. There will be many long runs of white pixels (represented as W), interspersed by short runs of black pixels (represented as B). The following row of pixels, when RLE is applied, would become:

```
WWWWWWWWWWWWBWWWWWWWWWWWWBBBWWWWWWWWWWWWWWWWWWWWWWWWBWWWWWWWWWWWWWW -> 12W1B12W3B24W1B14W
```

The original data is 67 characters long, while the compressed data is 18 characters long.

The crawler encodes the data at byte-level (a data value is a byte) as integers (not text). The maximum run length is 256, so the count fits in a single byte; add another `(value, count)` pair if the run is longer than than 256. If the crawler sent the previous example in a DATA packet, it would look like:

```
[0x00000000]    C5 05 00 18 00 01 44 41  54 41 0C 57 01 42 0C 57    |......DATA.W.B.W|
[0x00000010]    03 42 18 57 01 42 0E 57                             |.B.W.B.W|
```

## <a id="parity" />Error correction and detection

Hamming codes are a type of error correction code. Our file crawlers use the extended Hamming(255, 247) scheme, with even parity. The "extended" adds an extra bit for global parity. There are 256 total bits (255 + 1 for global parity) in each block, with 9 (8 + 1 for global parity) redundant bits (located at positions 0, 1, 2, 4, 8, 16, 32, 64, and 128). This gives us 247 (255 - 8, or 256 - 9) bits of data.

<sub>Even parity means that the number of 1 bits in the group must be divisible by 2 (hence the name 'even').</sub>

- Bit 0 covers the whole block, including other parity bits
- Parity bits have a position that is a power of 2 (only 1 bit set when written in binary)
  - Ex: Bit 8 is a parity bit, because 0b00001000 has a single set bit
- Every other bit is a data bit (two or more 1 bits)
  - Each data bit is in a unique set of two or more parity bits, determined by its position
  - Ex: Bit 9 (1001) is covered by the parity bits at positions 8 and 1
- Parity bits cover all bits where the bitwise AND of the parity bit's position and of the data bit's position is non-zero
  - Ex: parity bit 32 covers bits 32-63, 96-127, 160-191, 224-254 (where `bit_position & 32 != 0`)
- The combination of parity bits will give the position of the erroneous bit

<sub>NB: Assume that there cannot be more than 2 flipped bits per block.</sub>

Tables and formulas for extended Hamming(255, 247) can be found in the [extended_hamming_255_247.md](extended_hamming_255_247.md) file.

### <a id="parity_example" />Example

As an example, we'll look at an extended Hamming(15, 11) code, which has a block size of 16 and 11 data bits.

` `|Col 1|Col 2|Col 3|Col 4
---|---|---|---|---
<b>Row 1</b>|G<sub>0000</sub>|P<sub>0001</sub>|P<sub>0010</sub>|D<sub>0011</sub>
<b>Row 2</b>|P<sub>0100</sub>|D<sub>0101</sub>|D<sub>0110</sub>|D<sub>0111</sub>
<b>Row 3</b>|P<sub>1000</sub>|D<sub>1001</sub>|D<sub>1010</sub>|D<sub>1011</sub>
<b>Row 4</b>|D<sub>1100</sub>|D<sub>1101</sub>|D<sub>1110</sub>|D<sub>1111</sub>

<sub>G: global parity; it covers the entire block</sub>
<sub>P: parity bit; each covers 2 rows or 2 columns</sub>
<sub>D: data bit; contains the message to be transmitted</sub>

- P<sub>0001</sub> covers positions matching `xxx1`: 3<sub>0011</sub>, 5<sub>0101</sub>, 7<sub>0111</sub>, 9<sub>1001</sub>, 11<sub>1011</sub>, 13<sub>1101</sub>, 15<sub>1111</sub>
- P<sub>0010</sub> covers positions matching `xx1x`: 3<sub>0011</sub>, 6<sub>0110</sub>, 7<sub>0111</sub>, 10<sub>1010</sub>, 11<sub>1011</sub>, 14<sub>1110</sub>, 15<sub>1111</sub>
- P<sub>0100</sub> covers positions matching `x1xx`: 5<sub>0101</sub>, 6<sub>0110</sub>, 7<sub>0111</sub>, 12<sub>1100</sub>, 13<sub>1101</sub>, 14<sub>1110</sub>, 15<sub>1111</sub>
- P<sub>1000</sub> covers positions matching `1xxx`: 9<sub>1001</sub>, 10<sub>1010</sub>, 11<sub>1011</sub>, 12<sub>1100</sub>, 13<sub>1101</sub>, 14<sub>1110</sub>, 15<sub>1111</sub>
- G<sub>0000</sub> covers all positions, even the other parity bits

Looking closer, we can see a pattern:
- P<sub>0001</sub> covers columns 2 and 4
- P<sub>0010</sub> covers columns 3 and 4
- P<sub>0100</sub> covers rows 2 and 4
- P<sub>1000</sub> covers rows 3 and 4

This gives the following formulas:
- P<sub>0001</sub> = D<sub>0011</sub> ^ D<sub>0101</sub> ^ D<sub>0111</sub> ^ D<sub>1001</sub> ^ D<sub>1011</sub> ^ D<sub>1101</sub> ^ D<sub>1111</sub>
- P<sub>0010</sub> = D<sub>0011</sub> ^ D<sub>0110</sub> ^ D<sub>0111</sub> ^ D<sub>1010</sub> ^ D<sub>1011</sub> ^ D<sub>1110</sub> ^ D<sub>1111</sub>
- P<sub>0100</sub> = D<sub>0101</sub> ^ D<sub>0110</sub> ^ D<sub>0111</sub> ^ D<sub>1100</sub> ^ D<sub>1101</sub> ^ D<sub>1110</sub> ^ D<sub>1111</sub>
- P<sub>1000</sub> = D<sub>1001</sub> ^ D<sub>1010</sub> ^ D<sub>1011</sub> ^ D<sub>1100</sub> ^ D<sub>1101</sub> ^ D<sub>1110</sub> ^ D<sub>1111</sub>

Suppose we wish to send the following 11 bits: `11001011011`. We insert the data bits and get:

` `|Col 1|Col 2|Col 3|Col 4
---|---|---|---|---
<b>Row 1</b>|G<sub>0000</sub>|P<sub>0001</sub>|P<sub>0010</sub>|1<sub>0011</sub>
<b>Row 2</b>|P<sub>0100</sub>|1<sub>0101</sub>|0<sub>0110</sub>|0<sub>0111</sub>
<b>Row 3</b>|P<sub>1000</sub>|1<sub>1001</sub>|0<sub>1010</sub>|1<sub>1011</sub>
<b>Row 4</b>|1<sub>1100</sub>|0<sub>1101</sub>|1<sub>1110</sub>|1<sub>1111</sub>

Next, we compute the parity bits:
- P<sub>0001</sub> = 1<sub>0011</sub> ^ 1<sub>0101</sub> ^ 0<sub>0111</sub> ^ 1<sub>1001</sub> ^ 1<sub>1011</sub> ^ 0<sub>1101</sub> ^ 1<sub>1111</sub> = 1
- P<sub>0010</sub> = 1<sub>0011</sub> ^ 0<sub>0110</sub> ^ 0<sub>0111</sub> ^ 0<sub>1010</sub> ^ 1<sub>1011</sub> ^ 1<sub>1110</sub> ^ 1<sub>1111</sub> = 0
- P<sub>0100</sub> = 1<sub>0101</sub> ^ 0<sub>0110</sub> ^ 0<sub>0111</sub> ^ 1<sub>1100</sub> ^ 0<sub>1101</sub> ^ 1<sub>1110</sub> ^ 1<sub>1111</sub> = 0
- P<sub>1000</sub> = 1<sub>1001</sub> ^ 0<sub>1010</sub> ^ 1<sub>1011</sub> ^ 1<sub>1100</sub> ^ 0<sub>1101</sub> ^ 1<sub>1110</sub> ^ 1<sub>1111</sub> = 1

` `|Col 1|Col 2|Col 3|Col 4
---|---|---|---|---
<b>Row 1</b>|G<sub>0000</sub>|1<sub>0001</sub>|0<sub>0010</sub>|1<sub>0011</sub>
<b>Row 2</b>|0<sub>0100</sub>|1<sub>0101</sub>|0<sub>0110</sub>|0<sub>0111</sub>
<b>Row 3</b>|1<sub>1000</sub>|1<sub>1001</sub>|0<sub>1010</sub>|1<sub>1011</sub>
<b>Row 4</b>|1<sub>1100</sub>|0<sub>1101</sub>|1<sub>1110</sub>|1<sub>1111</sub>

To get even parity across the whole block, G<sub>0000</sub> should be 1. Our block with all parity bits set looks like:

` `|Col 1|Col 2|Col 3|Col 4
---|---|---|---|---
<b>Row 1</b>|1<sub>0000</sub>|1<sub>0001</sub>|0<sub>0010</sub>|1<sub>0011</sub>
<b>Row 2</b>|0<sub>0100</sub>|1<sub>0101</sub>|0<sub>0110</sub>|0<sub>0111</sub>
<b>Row 3</b>|1<sub>1000</sub>|1<sub>1001</sub>|0<sub>1010</sub>|1<sub>1011</sub>
<b>Row 4</b>|1<sub>1100</sub>|0<sub>1101</sub>|1<sub>1110</sub>|1<sub>1111</sub>

So when we add parity bits to `11001011011`, we get `1101010011011011`.

#### <a id='parity_1_flip' />1 bit flip

Suppose that bit 3<sub>0011</sub> is flipped during transmission and we receive the following block:

` `|Col 1|Col 2|Col 3|Col 4
---|---|---|---|---
<b>Row 1</b>|1<sub>0000</sub>|1<sub>0001</sub>|0<sub>0010</sub>|0<sub>0011</sub>
<b>Row 2</b>|0<sub>0100</sub>|1<sub>0101</sub>|0<sub>0110</sub>|0<sub>0111</sub>
<b>Row 3</b>|1<sub>1000</sub>|1<sub>1001</sub>|0<sub>1010</sub>|1<sub>1011</sub>
<b>Row 4</b>|1<sub>1100</sub>|0<sub>1101</sub>|1<sub>1110</sub>|1<sub>1111</sub>

Let's check our equations from above:
- P<sub>0001</sub>: 1 = 0<sub>0011</sub> ^ 1<sub>0101</sub> ^ 0<sub>0111</sub> ^ 1<sub>1001</sub> ^ 1<sub>1011</sub> ^ 0<sub>1101</sub> ^ 1<sub>1111</sub> (!!!)
- P<sub>0010</sub>: 0 = 0<sub>0011</sub> ^ 0<sub>0110</sub> ^ 0<sub>0111</sub> ^ 0<sub>1010</sub> ^ 1<sub>1011</sub> ^ 1<sub>1110</sub> ^ 1<sub>1111</sub> (!!!)
- P<sub>0100</sub>: 0 = 1<sub>0101</sub> ^ 0<sub>0110</sub> ^ 0<sub>0111</sub> ^ 1<sub>1100</sub> ^ 0<sub>1101</sub> ^ 1<sub>1110</sub> ^ 1<sub>1111</sub>
- P<sub>1000</sub>: 1 = 1<sub>1001</sub> ^ 0<sub>1010</sub> ^ 1<sub>1011</sub> ^ 1<sub>1100</sub> ^ 0<sub>1101</sub> ^ 1<sub>1110</sub> ^ 1<sub>1111</sub>

We can see that G<sub>0000</sub>, P<sub>0001</sub>, and P<sub>0010</sub> don't hold. We therefore know that bit 3<sub>0011</sub> was flipped, because `0001 | 0010 = 0011`. ORing/adding the positions of the parity bits that have an error gives the position of the errorneous bit.

<sub>NB: Hamming codes can also detect and correct a flipped parity bit, including G<sub>0000</sub></sub>

#### <a id='parity_2_flip' />2 bit flips

Suppose that bits 3<sub>0011</sub> and 14<sub>1110</sub> are flipped during transmission and we receive the following block:

` `|Col 1|Col 2|Col 3|Col 4
---|---|---|---|---
<b>Row 1</b>|1<sub>0000</sub>|1<sub>0001</sub>|0<sub>0010</sub>|0<sub>0011</sub>
<b>Row 2</b>|0<sub>0100</sub>|1<sub>0101</sub>|0<sub>0110</sub>|0<sub>0111</sub>
<b>Row 3</b>|1<sub>1000</sub>|1<sub>1001</sub>|0<sub>1010</sub>|1<sub>1011</sub>
<b>Row 4</b>|1<sub>1100</sub>|0<sub>1101</sub>|0<sub>1110</sub>|1<sub>1111</sub>

Let's check our equations from above:
- P<sub>0001</sub>: 1 = 0<sub>0011</sub> ^ 1<sub>0101</sub> ^ 0<sub>0111</sub> ^ 1<sub>1001</sub> ^ 1<sub>1011</sub> ^ 0<sub>1101</sub> ^ 1<sub>1111</sub> (!!!)
- P<sub>0010</sub>: 0 = 0<sub>0011</sub> ^ 0<sub>0110</sub> ^ 0<sub>0111</sub> ^ 0<sub>1010</sub> ^ 1<sub>1011</sub> ^ 0<sub>1110</sub> ^ 1<sub>1111</sub>
- P<sub>0100</sub>: 0 = 1<sub>0101</sub> ^ 0<sub>0110</sub> ^ 0<sub>0111</sub> ^ 1<sub>1100</sub> ^ 0<sub>1101</sub> ^ 0<sub>1110</sub> ^ 1<sub>1111</sub> (!!!)
- P<sub>1000</sub>: 1 = 1<sub>1001</sub> ^ 0<sub>1010</sub> ^ 1<sub>1011</sub> ^ 1<sub>1100</sub> ^ 0<sub>1101</sub> ^ 0<sub>1110</sub> ^ 1<sub>1111</sub> (!!!)

We can see that P<sub>0001</sub>, P<sub>0010</sub>, and P<sub>1000</sub> don't hold, but G<sub>0000</sub> does! This case means that there were 2 bit flips, but we can't find their positions. We need to ask the crawler to resend this packet.

## <a id="helpme"/>Help

Make sure to include the steps to compile and/or run your code. It can be a Makefile, a CMakeLists.txt, or even a list of shell commands. If I cannot easily compile your code, I will not grade it.

You are allowed to use the Internet, and your language's standard library. Nothing else. If I have to install a 3rd party lib to run your code, you will get 0 points.

The `processify.py` will not be useful to you. It's a decorator to run a function in a separate process.

For testing purposes, your crawler's behaviour can be controlled with environment variables. Invalid values are equivalent to not setting the variable.

* `CRWL_METADATA`: If set, the crawler will always send all metadata packets (MODE, SEQN) before transferring data.
* `CRWL_MODE`: If set, the crawler will always send a MODE packet with the specified value.
* `CRWL_SEQN`: If set, the crawler will always send a SEQN packet with the specified value.
* `CRWL_FORCE_OUT_OF_ORDER`: If set, the crawler will send some packets out of order.
* `CRWL_FORCE_ERROR`: If set, the crawler will put errors into the packets.
* `CRWL_FORCE_DUPLICATE`: If set, the crawler will upload a file that was already uploaded.
* `CRWL_NB_CRAWLERS`: The test script will spawn this many crawlers. The default is 2.
* `CRWL_NO_HAMMING`: The crawler will not compute the parity bits for each packet (they will not be included in the payload). The default is that parity bits are computed and inserted in the packets.
* `CRWL_NO_RLE`: The crawler will not run-length encode the data. The default is that it will be run length encoded.
* `CRWL_RX_TIMEOUT`: How long the crawler will wait (in seconds) for the server's response before throwing an error. The default is 5. This is also how long the crawler will wait after sending the last DATA packet.
* `CRWL_DEBUG`: If set, the crawler will print some debug data

Common pitfalls to avoid:
* Every integer sent over the network must be sent in network byte order (`man htons`)
* Every integer received from the network should be converted to host byte order (`man ntohs`)
* Redundant bits should be _removed_ from the received data before saving to disk
* Make sure the buffer to receive the crawler's requests is big enough (>= 508 bytes), else the packet is dropped
* The crawler does not end the message type with a null byte

### <a id="workflow"/>Workflow

The typical workflow for handling a single crawler could resemble this:
1. Receive a crawler's UPLD packet.
2. Receive the transfer's metadata, if any.
3. Receive DATA packet.
4. Reorder packet queue if need be.
5. Send sequence numbers of missed packets if any are missing.
6. Continue from step 3 until an empty DATA packet is received.

## <a id="grading"/>Grading

Requirement|Points
-----|----:
Handle a single file upload|20
Handle multiple file uploads from the same crawler|15
Handle multiple crawlers|10
Send the correcct responses to the crawler|10
Validate packets|15
Handle duplicate files|5
Handle compressed mode uploads|5
Correct 1-bit errors|5
Detect 2-bit errors|5
Handle out-of-order packets|5
Handle packet loss|5

Your competition director, Philippe Gorley
