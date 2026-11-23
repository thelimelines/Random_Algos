#pragma once

#include <cstddef>
#include <memory>
#include <random>
#include <vector>

namespace physics
{
constexpr unsigned windowSize = 1080;
constexpr float ballRadius = 8.f;
constexpr int ticksPerSecond = 60;
constexpr int substepsPerTick = 8;
constexpr int substepsPerSecond = ticksPerSecond * substepsPerTick;
constexpr float tickSeconds = 1.f / ticksPerSecond;
constexpr float stepSeconds = 1.f / substepsPerSecond;
constexpr float spawnX = 36.f;
constexpr float spawnY = windowSize / 10.f;

enum class CollisionMode
{
    Naive,
    Grid,
    Halo
};

struct Ball
{
    Ball(float x, float y, float vx, float vy)
        : x(x), y(y), previousX(x - vx * stepSeconds), previousY(y - vy * stepSeconds)
    {}

    float x;
    float y;
    float previousX;
    float previousY;
};

class Simulation
{
public:
    explicit Simulation(CollisionMode mode, std::vector<Ball> initialBalls = {});
    ~Simulation();

    void advance(bool spawnEnabled = true);
    void reset();
    const std::vector<Ball>& balls() const { return balls_; }
    unsigned workerCount() const;
    bool sameState(const Simulation& other) const;

private:
    struct CollisionWorkspace;
    void findCandidates();

    CollisionMode mode_;
    std::vector<Ball> balls_;
    std::mt19937 random_;
    std::size_t step_ = 0;
    std::unique_ptr<CollisionWorkspace> collision_;
};
}
