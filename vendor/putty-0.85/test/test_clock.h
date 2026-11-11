/* SPDX-License-Identifier: MIT */
#ifndef NEMO_TEST_CLOCK_H
#define NEMO_TEST_CLOCK_H
/* This target supplies the timer API itself instead of linking no-timing.c.
 * Time advances deterministically, including callbacks that schedule another
 * callback. No sleep or wall-clock timing is involved. */
typedef struct TestTimer {
    unsigned long due;
    timer_fn_t fn;
    void *ctx;
    bool active;
} TestTimer;

static TestTimer test_timers[256];
static unsigned long test_clock = 1000;

unsigned long schedule_timer(int ticks, timer_fn_t fn, void *ctx)
{
    unsigned long due = test_clock + (ticks > 0 ? ticks : 1);
    size_t free_slot = lenof(test_timers);
    for (size_t i = 0; i < lenof(test_timers); i++) {
        TestTimer *t = &test_timers[i];
        if (t->active && t->due == due && t->fn == fn && t->ctx == ctx)
            return due;
        if (!t->active && free_slot == lenof(test_timers))
            free_slot = i;
    }
    if (free_slot == lenof(test_timers)) {
        fputs("Test timer capacity exceeded\n", stderr);
        abort();
    }
    test_timers[free_slot] = (TestTimer){due, fn, ctx, true};
    return due;
}

void expire_timer_context(void *ctx)
{
    for (size_t i = 0; i < lenof(test_timers); i++)
        if (test_timers[i].ctx == ctx)
            test_timers[i].active = false;
}

unsigned long timing_last_clock(void)
{
    return test_clock;
}

static void advance_test_clock(unsigned long target)
{
    assert(target >= test_clock);
    for (;;) {
        size_t next = lenof(test_timers);
        for (size_t i = 0; i < lenof(test_timers); i++)
            if (test_timers[i].active && test_timers[i].due <= target &&
                (next == lenof(test_timers) ||
                 test_timers[i].due < test_timers[next].due))
                next = i;
        if (next == lenof(test_timers))
            break;
        TestTimer t = test_timers[next];
        test_timers[next].active = false;
        test_clock = t.due;
        t.fn(t.ctx, t.due);
    }
    test_clock = target;
}

#endif
