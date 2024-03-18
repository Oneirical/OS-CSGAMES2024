#include <stdint.h>

#define CSGAMES_MAX_PAYLOAD_SIZE 498

struct csgames_command_header {
    uint16_t magic_number;
    uint16_t payload_size;
    uint16_t crawler_id;
    char message_type[4];
};

struct csgames_upload_packet {
    csgames_command_header header;
    char filepath[255];
};

struct csgames_mode_packet {
    csgames_command_header header;
    char mode[10];
};

struct csgames_sequence_packet {
    csgames_command_header header;
    uint16_t sequence;
};

struct csgames_data_packet {
    csgames_command_header header;
    uint16_t upload_id;
    uint16_t sequence;
    uint8_t data[CSGAMES_MAX_PAYLOAD_SIZE - 2 * sizeof(uint16_t)];
};

union csgames_packet {
    struct csgames_command_header header;
    struct csgames_upload_packet upld;
    struct csgames_mode_packet mode;
    struct csgames_sequence_packet seqn;
    struct csgames_data_packet data;
    uint8_t bytes[CSGAMES_MAX_PAYLOAD_SIZE + sizeof(csgames_command_header)];
};