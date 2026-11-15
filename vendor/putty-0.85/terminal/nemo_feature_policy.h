/* SPDX-License-Identifier: MIT */
#ifndef NEMO_FEATURE_POLICY_H
#define NEMO_FEATURE_POLICY_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

enum NemoFeatureCategory {
    NEMO_FEATURE_COLOR, NEMO_FEATURE_FONT, NEMO_FEATURE_MOUSE,
    NEMO_FEATURE_PASTE, NEMO_FEATURE_TCAP, NEMO_FEATURE_TITLE,
    NEMO_FEATURE_WINDOW, NEMO_FEATURE_COUNT
};

/* Protocol operation numbers, including the gaps in XTWINOPS. */
enum NemoFeatureWindowOp {
    NEMO_FW_RESTORE=1, NEMO_FW_MINIMIZE=2, NEMO_FW_POSITION=3,
    NEMO_FW_SIZE_PIXELS=4, NEMO_FW_RAISE=5, NEMO_FW_LOWER=6,
    NEMO_FW_REFRESH=7, NEMO_FW_SIZE_CHARS=8, NEMO_FW_MAXIMIZE=9,
    NEMO_FW_FULLSCREEN=10, NEMO_FW_STATE=11, NEMO_FW_GET_POSITION=13,
    NEMO_FW_GET_PIXELS=14, NEMO_FW_SCREEN_PIXELS=15, NEMO_FW_CHAR_PIXELS=16,
    NEMO_FW_GET_CHARS=18, NEMO_FW_SCREEN_CHARS=19, NEMO_FW_ICON_TITLE=20,
    NEMO_FW_WIN_TITLE=21, NEMO_FW_PUSH_TITLE=22, NEMO_FW_POP_TITLE=23,
    NEMO_FW_LINES=24, NEMO_FW_COLUMNS=25, NEMO_FW_XPROP=26,
    NEMO_FW_GET_SELECTION=27, NEMO_FW_SET_SELECTION=28,
    NEMO_FW_GET_CHECKSUM=29, NEMO_FW_SET_CHECKSUM=30, NEMO_FW_STATUS_LINE=31
};
#define NEMO_FEATURE_BIT(n) (UINT64_C(1) << (n))
#define NEMO_FEATURE_POLICY_REPLY_MAX 1024

/* A transient snapshot, not stored on each terminal or text cell. */
typedef struct NemoFeaturePolicy {
    unsigned enabled;
    uint64_t supported[NEMO_FEATURE_COUNT];
    uint64_t restricted[NEMO_FEATURE_COUNT];
} NemoFeaturePolicy;

/* Zero means ignored request or insufficient output capacity. No allocation,
 * partial reply, mutation of permissions, or null-terminated input required. */
size_t nemo_feature_policy_reply(const NemoFeaturePolicy *, unsigned number,
    const char *payload, size_t length, bool utf8, bool bel,
    char *reply, size_t capacity);
#endif
