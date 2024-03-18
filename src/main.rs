use std::net::{TcpListener, TcpStream};
use std::io::{Read, Write, BufWriter};
use std::fs::OpenOptions;
use std::thread;

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

#[derive(Clone, Copy)]
enum Mode {
    Block,
    Compressed,
}

enum Packet {
    UPLD { crawler_id: u16, file_path: String },
    MODE { mode: Mode },
    SEQN { seq_num: u16 },
    DATA { upload_id: u16, seq_num: u16, data: Vec<u8> },
}

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

fn send_error_response(socket: &mut TcpStream, message: &str) -> std::io::Result<()> {
    let response = format!("IAMERR\x00{:02X}{}", message.len() + 4, message);
    socket.write_all(response.as_bytes())?;
    Ok(())
}

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
