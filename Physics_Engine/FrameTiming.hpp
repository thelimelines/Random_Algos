#pragma once

class FrameTiming
{
public:
    bool recordFrame(double seconds)
    {
        elapsed_ += seconds;
        ++frames_;
        if (elapsed_ < 0.25)
            return false;

        fps_ = frames_ / elapsed_;
        // Allow a little headroom before resuming to avoid toggling near 30 FPS.
        spawningPaused_ = fps_ < (spawningPaused_ ? 32.0 : 30.0);
        elapsed_ = 0.0;
        frames_ = 0;
        return true;
    }

    double fps() const { return fps_; }
    double frameMilliseconds() const { return 1000.0 / fps_; }
    bool spawningPaused() const { return spawningPaused_; }

private:
    double elapsed_ = 0.0;
    int frames_ = 0;
    double fps_ = 0.0;
    bool spawningPaused_ = false;
};
