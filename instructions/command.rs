use std::mem;

const CSGAMES_MAX_PAYLOAD_SIZE: usize = 498;

struct csgames_command_header {
    magic_number: u16,
    payload_size: u16,
    crawler_id: u16,
    message_type: [u8; 4],
}

struct csgames_upload_packet {
    header: csgames_command_header,
    filepath: [char; 255],
}

struct csgames_mode_packet {
    header: csgames_command_header,
    mode: [char; 10],
}

struct csgames_sequence_packet {
    header: csgames_command_header,
    sequence: u16,
}

struct csgames_data_packet {
    header: csgames_command_header,
    upload_id: u16,
    sequence: u16,
    data: [u8; CSGAMES_MAX_PAYLOAD_SIZE - 2 * mem::size_of::<u16>()],
}

enum csgames_packet {
    upld(csgames_upload_packet),
    mode(csgames_mode_packet),
    seqn(csgames_sequence_packet),
    data(csgames_data_packet),
    bytes([u8; CSGAMES_MAX_PAYLOAD_SIZE + mem::size_of::<csgames_command_header>()])
}