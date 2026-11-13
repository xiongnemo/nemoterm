/* SPDX-License-Identifier: MIT */
#ifndef NEMO_SHELL_MARKS_H
#define NEMO_SHELL_MARKS_H

#define NEMO_SHELL_MARK_MAX 256
#define NEMO_SHELL_TEXT_MAX 4096
#define NEMO_SHELL_TEXT_BUDGET 65536
#define NEMO_SHELL_OSC_MAX 16384

enum NemoShellPhase {
    NEMO_SHELL_PROMPT, NEMO_SHELL_COMMAND, NEMO_SHELL_OUTPUT,
    NEMO_SHELL_END, NEMO_SHELL_NONE
};
typedef struct NemoShellPoint {
    int x, y; /* main-screen cells; negative rows are retained history */
    bool valid, truncated;
} NemoShellPoint;
typedef struct NemoShellCommand {
    uint64_t id;
    NemoShellPoint point[4];
    enum NemoShellPhase phase;
    bool finished, exit_known;
    int64_t exit_code;
    char *text; /* optional untrusted OSC 633 E text, never an instruction */
    size_t text_bytes;
} NemoShellCommand;
typedef struct NemoShellMarks {
    NemoShellCommand *commands; /* oldest first, allocated on first mark */
    size_t count, capacity, text_bytes;
    uint64_t next_id, active_id;
    bool is_windows, rich_detection;
} NemoShellMarks;

void nemo_shell_marks_clear(NemoShellMarks *);
size_t nemo_shell_marks_memory(const NemoShellMarks *);
bool nemo_shell_marks_update(NemoShellMarks *, unsigned osc,
                             const char *, size_t, int x, int y);
void nemo_shell_marks_rows(NemoShellMarks *, int first, int last, int delta);
void nemo_shell_marks_scroll(NemoShellMarks *, int left, int right,
                            int top, int bottom, int delta,
                            bool full_width, bool into_history);
void nemo_shell_marks_shift(NemoShellMarks *, int left, int right,
                           int top, int bottom, int delta);
const NemoShellCommand *nemo_shell_marks_lookup(const NemoShellMarks *, uint64_t);
/* Ranges are half-open, logical cell positions; retained history is clipped. */
bool nemo_shell_marks_range(const NemoShellCommand *, bool output,
                           int first_row, int last_row,
                           NemoShellPoint *start, NemoShellPoint *end);
uint64_t nemo_shell_marks_neighbour(const NemoShellMarks *, int direction,
                                  int x, int y, int first_row, int last_row,
                                  NemoShellPoint *);
#endif
