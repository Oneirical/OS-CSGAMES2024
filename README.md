> "We have discovered a file crawler in a mysterious PC containing an unfamiliar OS. The resistance believes that it could contain crucial information against the green threat. Therefore, your mission is to interact with it and extract all its secrets. But be careful: who knows what defence mechanisms this device may have?"

Well? How hard could this possibly be?

Spoiler: very much so.

# Background

On the 15-16-17 weekend of March 2024, I participated in the [CS Games](https://fr.wikipedia.org/wiki/Jeux_des_sciences_de_l%27informatique) competition for the first time, the largest undergraduate computer science contest in the noble province of Québec. I expected questionable odours, high levels of introversion and extremely difficult challenges. It appears only the latter conformed to my expectations, for the contenders truly did know how to party with the vast array of costumes, singing and loud electronic music at their disposition. Much to the chagrin of my fragile and sensitive ears.

I "selected" the challenges **Operating Systems, Modular Development and High Performance Computing**. Since I am the only person who could not attend the Concordia introductory meeting, my team leaders chose for me - but I must celebrate their skill at making decisions in my place, for I thoroughly enjoyed two out of the three. Sorry, Modular Development organizers, but I'd rather NOT drown in a deluge of UI micro-buttons and programming syntax hauled straight from the 1970s.

Mildly disappointed at the end of the competition, I sincerely thought I was going to win nothing. My bewildered face is now immortalized on the podium photo of the Operating Systems category, in the highly unexpected ranking of first place.

This post will reveal to you a fragment of the endured suffering.

# The Assignment

[You may read here the instructions given to me and my teammate, Jaspreet, at the beginning of this 3 hour battle.](https://github.com/Oneirical/OS-CSGAMES2024/blob/master/instructions/os.en.md)

First course of action: dumb it down a bit so that it may be parsed by my feeble brain where 50% of storage is clogged by fluffiness and pictures of cute cats. Clearly, we are dealing here with a MACHINE that RECEIVES THINGS, does some stuff with them, and outputs a transformed version of those THINGS.

Also known as a "server". Yeah, I know what those are, right? I used to play Minecraft all the time on those! I can choose any programming language for this task...

The answer is obviously Rust. Sure, it has unimportant features like "multithreading", "memory safety" or "static typing", but what I truly care about is how its proponents occasionally possess profile pictures on Github of cute Pokémon wearing adorable bowties and ribbons. And, if someone got a job in technology with this little professionalism, then I would be wise to follow their every word of advice.

The challenge allows for use of any tool, including LLMs and full internet access. Sweet! It's just like working at a real job.

> Even ChatGPT won't save you. Good luck. - Mr Gorley, challenge organizer

# Things, In And Out

> Warning: I am a Biology undergraduate student self-teaching myself technology to escape the gulf of academia. I make mistakes. If anything in this post is wrong, I genuinely want to be corrected so that I may learn. Contact me at my email: julien-robert@videotron.ca, or message me on Discord - my username is "oneirical".

So, according to the intructions, the poor file crawler is currently throwing its delivery crates ("packets") in the abyss known as "port 7331" where no one cares about it or gives it any attention. Let us fix that.

```rust
fn main() -> std::io::Result<()> {
    let listener = TcpListener::bind("127.0.0.1:7331")?;

    for stream in listener.incoming() {
        match stream {
            Ok(stream) => {
                thread::spawn(move || {
                    handle_connection(stream).unwrap();
                });
            }
            Err(e) => {
                eprintln!("Failed to accept connection; err = {:?}", e);
            }
        }
    }

    Ok(())
}
```

Now, I have no idea what a TCP or UDP stream is. I don't really remember what they mean, probably something like Tragically Cute Puppies or Unrealistically Desirable Pets. What I did, however, find out, is that when it comes to these kinds of server challenges, you'll usually want to make your connection follow the TCP type. Put a metaphorical pin in that, this will be relevant later.

Each "stream" is like a conveyor belt transporting packets into my little letterbox. All such streams should be correct (marked as "Ok"), in which case a "thread" will spawn to start taking care of the deliveries, like a ~~loyal servant~~ volunteer assigned to unpacking the delivery crates. This thread-worker needs to be able to actually touch the crates to do anything, so the "move" keyword transmits ownership of the data to them! Let's see what is happening inside the other end of the stream-conveyor-belt.

## Packets Of All Shapes And Sizes

```rust
enum Packet {
    UPLD { crawler_id: u16, file_path: String },
    MODE { mode: Mode },
    SEQN { seq_num: u16 },
    DATA { upload_id: u16, seq_num: u16, data: Vec<u8> },
}

#[derive(Clone, Copy)]
enum Mode {
    Block,
    Compressed,
}
```

Not all packets serve the same purpose! We want that juicy intel contained in those DATA packets, yes, but such precious payload is to be handled with care. To prepare ourselves, we have:

- UPLD packets announcing the arrival of a fresh delivery. They contain the identification number of the crawler (conveyor belt) from where the delivery is coming, and the file path in the source OS ("country of origin") from which the data is getting extracted.
- MODE packets only announce whether or not the incoming data is compressed and needs to have some water splashed onto it to revert to its original form, or if it's good as it currently is. Note the two Mode enums dictating this.
- SEQN packets contain the "sequence number" of the packets. I am not as confident about these, but I believe they are counting what is the current number of DATA packets received, and if, for example, the next one will be the fifth or tenth one.

## Let's Unpack This

```rust
fn handle_connection(mut stream: TcpStream) -> std::io::Result<()> {
    let mut buffer = [0; 508]; // Maximum packet size
    let mut mode: Mode;

    loop {
        let n = match stream.read(&mut buffer) {
            Ok(n) if n == 0 => return Ok(()), // Connection closed
            Ok(n) => n,
            Err(e) => {
                eprintln!("Failed to read from socket; err = {:?}", e);
                return Err(e);
            }
        };

        // Parse the packet
        let packet = parse_packet(&buffer[..n]);
        match packet {
            Ok(packet) => {
                // Handle the packet
                mode = match packet {
                    Packet::MODE { mode } => {
                        mode
                    },
                    _ => Mode::Block,
                };
                handle_packet(&mut stream, packet, mode)?;
            }
            Err(e) => {
                eprintln!("Failed to parse packet; err = {:?}", e);
                // Send error response
                send_error_response(&mut stream, "Failed to parse packet")?;
            }
        }
    }
}
```

Have a glance inside our "volunteer"'s crate-unpacking room. Because there is no such thing as sensible work-life balance in MY factory, their task continues eternally with the "loop" keyword (same thing as "while true") until they are finally done and no further packets are coming out of the stream. The "n" variable is monitoring how many bytes are currently on the stream - how many crates remain on the conveyor belt, if you will. n = 0 returns Ok(()) and terminates our poor worker's employment.

"508" is the maximum size of a Packet, measured in bytes.

First, packets are **parsed**. This is because the shipping company sending these crates to us is laughably incompetent, and is basically just throwing a bunch of hexadecimal numbers on the conveyor belts wrapped in flimsy plastic packaging. The only way to identify where the crates begin and end, and what they actually are (UPLD, MODE, etc.) is through their **header**, a 10-byte sequence containing:

* 2 bytes: Magic number 0xC505
* 2 bytes: Total packet size, including header
* 2 bytes: Crawler identifier
* 4 bytes: Command name in ASCII

Basically, it's some cheap paper stickers slapped on top of the incoming transmission. We can do better. The "parse_packet" function makes all those messy bytes get tucked into a pristine box - the Packet enum shown earlier (UPLD, MODE, etc.) - all safe and sound for processing :3

I will demonstrate its inner workings in the following chapter. For now, the neatly processed Packet arrives in "match packet", where a quick check verifies if our esteemed volunteer did their job correctly. Yes, sometimes, the incoming data contains spiky or dangerous things poking out - most importantly "bit flips" causing erronous tagging. This is a part of the assignment! Should that be detected by "parse_packet", the "match packet" will throw the suspicious delivery into the incinerator of "send_error_response", where it shall be destroyed:

```rust
fn send_error_response(socket: &mut TcpStream, message: &str) -> std::io::Result<()> {
    let response = format!("IAMERR\x00{:02X}{}", message.len() + 4, message);
    socket.write_all(response.as_bytes())?;
    Ok(())
}
```

Hopefully, the next packet will fare better than its predecessor.

Let us return our attention to jobs well done - instances of "Ok(packet)". First, we check if we are currently dealing with a MODE packet - if yes, change the current active mode to match it - this will enable or disable the miraculous Decompressor 9000 located inside "handle_packet". We shall return to that later.

## Nice And Tidy Boxes

```rust
fn parse_packet(data: &[u8]) -> Result<Packet, &'static str> {
    // Check if the data is long enough to contain a header
    if data.len() < 10 {
        return Err("Packet too short");
    }

    // Parse the header
    let magic_number = u16::from_be_bytes([data[0], data[1]]);
    let total_packet_size = u16::from_be_bytes([data[2], data[3]]);
    let crawler_id = u16::from_be_bytes([data[4], data[5]]);
    let command_name = &data[6..10];

    // Validate the magic number
    
    if magic_number != 0xC505 {
        return Err("Invalid magic number");
    }

    // Validate that the received data is of the expected length
    if data.len() != total_packet_size as usize {
        return Err("Packet size mismatch");
    }

    // Determine the packet type based on the command name
    match command_name {
        b"UPLD" => {
            // Parse the UPLD packet
            let file_path = String::from_utf8_lossy(&data[10..]).to_string();
            Ok(Packet::UPLD { crawler_id, file_path })
        },
        b"MODE" => {
            // Parse the MODE packet
            let new_mode = match String::from_utf8_lossy(&data[10..]).as_ref() {
                "block" => Mode::Block,
                "compressed" => Mode::Compressed,
                _ => Mode::Block,
            };
            Ok(Packet::MODE { mode: new_mode })
        },
        b"SEQN" => {
            // Parse the SEQN packet
            if data.len() < 12 {
                return Err("Packet too short for SEQN");
            }
            let seq_num = u16::from_be_bytes([data[10], data[11]]);
            Ok(Packet::SEQN { seq_num })
        },
        b"DATA" => {
            // Parse the DATA packet
            if data.len() < 14 {
                return Err("Packet too short for DATA");
            }
            let upload_id = u16::from_be_bytes([data[10], data[11]]);
            let seq_num = u16::from_be_bytes([data[12], data[13]]);
            let data = data[14..].to_vec();
            Ok(Packet::DATA { upload_id, seq_num, data })
        },
        _ => Err("Unknown command"),
    }
}
```

Ah, the glorious packaging facility. Where the unruly and chaotic come to be crushed and rearranged into flawless order and conformity.

First, we ensure that the header - that flimy paper tag - actually exists. We check that at least 10 bytes are present, then begin slotting them into their respective categories. "from_be_bytes" is swapping out those pesky hexadecimal tags (C5 05 00 1B 00 01 55 50, ewww!) into a glorious human-readable number.

We then check that 1. the magic number is present, and that 2. the packet size written in the header actually corresponds to its real weight. If you've played Papers Please, it's just like weighing people at the customs on a scale to make sure they aren't hiding any contraband.

Should everything appear in order, we then package the contents! The "b" before each match statement is parsing the Packet type as a "byte string" - because the aforementioned incompetent packaging company, of course, just HAD to give us numbers, and not human-readable letters!

Cracking open what is inside the Packet allows us to fill up each field of the Packet enum (for example, DATA contains upload_id, seq_num and data). This finalized version is what is shipped to "handle_packet", covered in the next chapter.

## Payment Received

```rust
fn handle_packet(socket: &mut TcpStream, packet: Packet, mode: Mode) -> std::io::Result<()> {
    match packet {
        Packet::UPLD { crawler_id, file_path } => {
            // Acknowledge the upload
            let response = format!("UPLOADING\x00{:02X}", crawler_id);
            socket.write_all(response.as_bytes())?;
            Ok(())
        }
        Packet::MODE { mode } => {
            // Acknowledge the MODE packet
            let response = format!("METADATAMODE");
            socket.write_all(response.as_bytes())?;
            Ok(())
        }
        Packet::SEQN { seq_num } => {
            // Acknowledge the SEQN packet
            let response = format!("METADATASEQN");
            socket.write_all(response.as_bytes())?;
            Ok(())
        }
        Packet::DATA { upload_id, seq_num, mut data } => {
            // Handle DATA packet
            match mode {
                Mode::Block => {
                    // Handle block mode data
                },
                Mode::Compressed => {
                    // Handle compressed mode data
                    data = decompress_rle(&data);
                },
            }
            handle_data_packet(socket, upload_id, seq_num, data)
        }
    }
}
```

Receiving an UPLD, MODE or SEQN packet isn't very complicated. We pretty much only need to scream out that we got it, and it stops there. In the case of MODE packets, we already used its contents to swap the current active mode to Block or Compressed. DATA Packets are much more interesting...

First, they may or may not face the aforementioned Decompressor 9000. Observe, and be awed:

```rust
fn decompress_rle(data: &[u8]) -> Vec<u8> {
    let mut result = Vec::new();
    let mut index = 0;

    while index < data.len() {
        let value = data[index];
        let count = data[index + 1];
        result.resize(result.len() + count as usize, value);
        index += 2;
    }

    result
}
```

> "RLE is a form of lossless data compression in which runs (a run is sequence of consecutive values that are the same) of data are stored as a single count and data value.

I'm sorry, dear Mr Gorley - the competition organizer - but my hands were already quite full. I just looked up RLE decompression online, and translated the code into Rust. Forgive me, Linus Torvalds.

Following this process, DATA packets are sent to the final step of their journey:

```rust
fn handle_data_packet(socket: &mut TcpStream, upload_id: u16, seq_num: u16, data: Vec<u8>) -> std::io::Result<()> {
    
    let clean_data = remove_redundant_bits(&data);
    
    // Example: Write data to a file named after the upload_id
    let file_path = format!("upload_{}.bin", upload_id);
    let mut file = OpenOptions::new()
        .write(true)
        .append(true)
        .create(true)
        .open(file_path)?;

    let mut writer = BufWriter::new(file);
    writer.write_all(&clean_data)?;

    // If the data is empty, this is the end of the file transfer
    let file_path = format!("upload_{}.bin", upload_id);
    if data.is_empty() {
        // Send a response indicating the upload is complete
        let response = format!("UPLOAD END\x00{}", file_path);
        socket.write_all(response.as_bytes())?;
    }

    Ok(())
}
```

That "clean_data" step is a real brain liquefier. I'll come back to it later, I still do not fully understand it.

In order to capture that sweet intel, we need a place to store it. That is a file - possibly the most "Operating Systems" part of this challenge... As far as I am aware, most of the work done so far is more in the realm of Networking. And not the "talking to ambitious entrepreneurs at a fancy cocktail" type, I had my fair share of that one too at the CS Games ending banquet.

This file has full permissions, and has the entire contents of the data field of the DATA packet dumped into it. The end of this task is announced with the glorious victory chant of "UPLOAD END". Such celebrations must not last long - the next packet awaiting processing is already on the way...

## The Part Where It Sucked

Alright, so:

```rust
fn remove_redundant_bits(data: &[u8]) -> Vec<u8> {
    let mut result = Vec::new();
    let mut buffer = 0u16; // Temporary buffer to hold 2 bytes of data
    let mut bit_count = 0; // Keeps track of the number of bits processed

    for &byte in data {
        buffer = (buffer << 8) | (byte as u16); // Shift the buffer and add the new byte
        bit_count += 8; // Increment the bit count

        // Process 2 bytes of data at a time
        while bit_count >= 9 {
            // Extract 9 bits from the buffer
            let value = (buffer >> (bit_count - 9)) & 0x1FF; // Mask to keep only the last 9 bits
            result.push(value as u8); // Add the value to the result
            bit_count -= 9; // Update the bit count
        }
    }

    // Handle any remaining bits in the buffer
    if bit_count > 0 {
        let value = buffer & ((1 << bit_count) - 1); // Mask to keep only the last bit_count bits
        result.push(value as u8); // Add the value to the result
    }

    result
}
```

This is my attempt at making SOMETHING that would somewhat resemble the challenge requirement about Hamming codes. That part could have been written in Swahili and I would have probably understood it better.

I mean, just look at this:

> We can see that G<sub>0000</sub>, P<sub>0001</sub>, and P<sub>0010</sub> don't hold. We therefore know that bit 3<sub>0011</sub> was flipped, because `0001 | 0010 = 0011`. ORing/adding the positions of the parity bits that have an error gives the position of the errorneous bit.

I beg your pardon?

In the challenge description, there is this tiny line of text: "Redundant bits should be *removed* from the received data before saving to disk". I wondered if that had anything to do with "Hamming error correction". This resulted in hacked-together code in the final 30 minutes of the challenge, knit together from StackOverflow and LLM outputs. I understand what it does - it repeatedly combines the last byte in each buffer with a new byte, preparing for the next 9-bit extraction. This effectively makes little bundles of 9 bits and will drop any overflowing or redundant bits not part of the bundling process.

I'm pretty sure this has nothing to do with the Hamming-thingimagibob. I would obviously spend time and effort learning it in an actual job, but it wasn't something I could fit within the 3 hour time delay.

## Final Scoring

I was told my final score was 48/58, which *really* surprised me. I was imagining every other university team flawlessly implementing that Hamming error correction feature and annihilating us.

There was a Python script provided with the challenge, meant to "test" our server. However, it contained more bugs than my previous internship in entomological research, so I disregarded it entirely. Jaspreet, my teammate, had the brilliant idea to test the connection by simply plugging the IP address in the web browser, which gave us a big confidence boost when we found out the packet input was indeed successful. However, this was *not* real testing. I pretty much shipped the entire code for review in pure YOLO action.

It appears other teams DID manage to fix and use the script. They listened to the outgoing connection with Wireshark, and found out the protocol in use was UDP, and *not* TCP like we chose. I got crushed when I first heard this, as this would basically mean that our entire program would not work at all. At this point, I became convinced of my utmost failure.

However, the judge, in his magnanimity, only deducted a few points for this. After all, as far as I'm aware, changing the protocol wouldn't be so hard - just a matter of swapping out a function here and there.

The Université de Montréal team, who came in second place, visited me after the announcement of victory, saying that they found it quite weird that they did not get first place. They mentioned how they managed to implement every feature, including Hamming correction, and that they tested their code extensively using a modified version of the Python script. In fact, I remember them spending a LOT of time debugging it and showing newfound mistakes to the competition organizer. 

Personally, I preferred to use that time to polish the error handling of my server. Testing isn't as mandatory in Rust - if the compiler accepts it, is has a good chance of working on the first try!

Anyhow, I invite the UdeM team, who may be reading this, to open source their code like I did. I am intrigued to see how you two managed to implement that mysterious Hamming error correction feature.

# Special Thanks

- Jaspreet, my teammate for this challenge. You may not know Rust, but I am glad you agreed to let me use it for our code. Your ideas and discussions really propelled the project forwards, and your idea near the end to use a web browser to test the connection removed so much stress off my shoulders!

> "It's actually making me want to learn rust right now."

- [Evie](https://github.com/eievui5/), my most highly esteemed mentor and grand Rust arch-sorceress. Working on [RGBFIX](https://github.com/ISSOtm/rsgbds/pull/2) - a Game Boy ROM fixing tool - under your guidance before attempting this challenge helped *tremendously*, from proper error handling, to read/write operations, and, of course, parsing hexadecimal headers. Beyond your knowledge, you are also an amazing friend, and talking to you is one of the things I look the most forward to daily.

> I’m really happy for you. I can’t believe you were convinced you failed and then got first place :3

*If you enjoyed this writeup, feel free to contact me! I am currently looking for:*

- *Summer internships*
- *Full time positions after April 2025*
- *People to join my Northsec team - no large proficiency in security required, but the drive to learn about technology is mandatory*

*Discord: oneirical*
*Email: julien-robert@videotron.ca*