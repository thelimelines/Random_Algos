#include "FrameTiming.hpp"
#include "Simulation.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <vector>

namespace
{
bool checkFrameTimingAndSpawning()
{
    FrameTiming timing;
    const auto sampleAt = [&](double fps) {
        while (!timing.recordFrame(1.0 / fps))
        {
        }
        return timing.spawningPaused();
    };
    const bool measuredCorrectly = !sampleAt(60.0) && sampleAt(25.0)
        && std::abs(timing.frameMilliseconds() - 40.0) < 0.01
        && sampleAt(31.0) && !sampleAt(40.0);
    if (!measuredCorrectly)
        return false;

    // A paused emitter still advances a ball through unobstructed flight.
    constexpr int steps = 3 * physics::substepsPerSecond / 2;
    physics::Simulation sim(physics::CollisionMode::Grid, {{36.f, 100.f, 620.f, 40.f}});
    for (int step = 0; step < steps; ++step)
        sim.advance(false);

    if (sim.balls().size() != 1 || std::abs(sim.balls()[0].x - 966.f) > 1.f
        || std::abs(sim.balls()[0].y - 971.125f) > 2.f)
        return false;

    sim.advance(true);
    return sim.balls().size() == 2;
}

class OverlapProbe
{
public:
    float measure(const std::vector<physics::Ball>& balls)
    {
        constexpr float diameter = 2.f * physics::ballRadius;
        indices_.resize(balls.size());
        std::iota(indices_.begin(), indices_.end(), std::size_t{0});
        std::sort(indices_.begin(), indices_.end(), [&](std::size_t first, std::size_t second) {
            return balls[first].x < balls[second].x;
        });

        // Sweep left to right independently of the solver's collision grid.
        float nearestSquared = diameter * diameter;
        for (std::size_t first = 0; first < indices_.size(); ++first)
        {
            const auto& a = balls[indices_[first]];
            for (std::size_t second = first + 1; second < indices_.size(); ++second)
            {
                const auto& b = balls[indices_[second]];
                const float dx = b.x - a.x;
                if (dx * dx >= nearestSquared)
                    break;

                const float dy = b.y - a.y;
                nearestSquared = std::min(nearestSquared, dx * dx + dy * dy);
            }
        }
        return diameter - std::sqrt(nearestSquared);
    }

private:
    std::vector<std::size_t> indices_;
};

bool checkBoundaryContacts()
{
    // The first four pairs cross a vertical edge, a horizontal edge, and both
    // tile corner diagonals. The remaining pairs exercise walls and equal centers.
    const std::vector<physics::Ball> initial{
        {184, 90, 0, 0}, {176, 90, 0, 0},
        {90, 176, 0, 0}, {90, 184, 0, 0},
        {356, 176, 0, 0}, {364, 184, 0, 0},
        {544, 356, 0, 0}, {536, 364, 0, 0},
        {8, 1054, -20, 0}, {8, 1062, -20, 0},
        {800, 800, 0, 0}, {800, 800, 0, 0},
        {950, 1064, 0, 0}, {950, 1072, 0, 0}
    };
    physics::Simulation naive(physics::CollisionMode::Naive, initial);
    physics::Simulation grid(physics::CollisionMode::Grid, initial);
    physics::Simulation halo(physics::CollisionMode::Halo, initial);

    for (int step = 1; step <= 256; ++step)
    {
        naive.advance();
        grid.advance();
        halo.advance();
        if (!naive.sameState(grid) || !grid.sameState(halo))
        {
            std::cerr << "Boundary scenario mismatch at substep " << step << '\n';
            return false;
        }

        if (step == 1)
        {
            const auto& balls = halo.balls();
            for (std::size_t id = 0; id < initial.size(); id += 2)
            {
                const float dx = balls[id + 1].x - balls[id].x;
                const float dy = balls[id + 1].y - balls[id].y;
                const float minimumDistance = 2.f * physics::ballRadius - 0.02f;
                if (dx * dx + dy * dy < minimumDistance * minimumDistance)
                {
                    std::cerr << "Unresolved boundary scenario pair at index " << id << '\n';
                    return false;
                }
            }
        }
    }
    return true;
}

bool checkRestingPile()
{
    std::vector<physics::Ball> initial;
    constexpr float diameter = 2.f * physics::ballRadius;
    for (int row = 0; row < 12; ++row)
    {
        initial.emplace_back(950.f, physics::windowSize - physics::ballRadius - row * diameter,
                             0.f, 0.f);
    }

    physics::Simulation grid(physics::CollisionMode::Grid, initial);
    float peakSpeed = 0.f;
    for (int step = 0; step < physics::substepsPerSecond; ++step)
    {
        grid.advance();
        if (step >= physics::substepsPerSecond / 2)
        {
            for (std::size_t id = 0; id < initial.size(); ++id)
            {
                const auto& ball = grid.balls()[id];
                const float dx = ball.x - ball.previousX;
                const float dy = ball.y - ball.previousY;
                peakSpeed = std::max(peakSpeed, std::sqrt(dx * dx + dy * dy) / physics::stepSeconds);
            }
        }
    }
    const float overlap = OverlapProbe{}.measure(grid.balls());
    std::cout << "Resting stack: peak settled speed " << peakSpeed
              << " px/s, final overlap " << overlap << " px.\n";
    return peakSpeed < 8.f && overlap < 0.5f;
}
}

int runBenchmark()
{
    if (!checkFrameTimingAndSpawning())
    {
        std::cerr << "Frame timing, spawn control or launch motion check failed.\n";
        return 1;
    }
    std::cout << "Frame timing, spawn control and launch motion passed.\n";

    if (!checkBoundaryContacts())
        return 1;
    std::cout << "Boundary scenario: all three methods matched for 256 substeps.\n";

    if (!checkRestingPile())
    {
        std::cerr << "Resting pile did not settle within the speed and overlap limits.\n";
        return 1;
    }

    using Clock = std::chrono::steady_clock;
    using Milliseconds = std::chrono::duration<double, std::milli>;
    constexpr int firstMinute = 60 * physics::substepsPerSecond;
    constexpr int substeps = 105 * physics::substepsPerSecond;
    constexpr float maxFrameOverlap = 1.f;
    physics::Simulation grid(physics::CollisionMode::Grid);
    physics::Simulation halo(physics::CollisionMode::Halo);
    Milliseconds gridTime{};
    Milliseconds haloTime{};
    OverlapProbe probe;
    float worstOverlap = 0.f;
    float firstMinuteOverlap = 0.f;
    float currentOverlap = 0.f;
    int worstFrame = 0;
    const auto timedStep = [](physics::Simulation& simulation, Milliseconds& total) {
        const auto start = Clock::now();
        simulation.advance();
        total += Clock::now() - start;
    };

    for (int step = 1; step <= substeps; ++step)
    {
        // Alternate which simulation runs first to avoid a fixed timing order.
        if (step % 2 == 0)
        {
            timedStep(grid, gridTime);
            timedStep(halo, haloTime);
        }
        else
        {
            timedStep(halo, haloTime);
            timedStep(grid, gridTime);
        }

        if (!grid.sameState(halo))
        {
            std::cerr << "Grid and halo mismatch at substep " << step << '\n';
            return 1;
        }
        if (step % physics::substepsPerTick == 0)
        {
            currentOverlap = probe.measure(grid.balls());
            if (currentOverlap > maxFrameOverlap)
            {
                std::cerr << "Excessive overlap at frame " << step / physics::substepsPerTick
                          << " (" << currentOverlap << " px, limit " << maxFrameOverlap << " px)\n";
                return 1;
            }
            if (currentOverlap > worstOverlap)
            {
                worstOverlap = currentOverlap;
                worstFrame = step / physics::substepsPerTick;
            }
        }
        if (step == firstMinute)
            firstMinuteOverlap = worstOverlap;
    }

    std::cout << "Spawn benchmark: bit-for-bit match for " << substeps << " substeps, "
              << grid.balls().size() << " balls at the finish.\n"
              << std::fixed << std::setprecision(2)
              << "Deepest frame overlap in the first 60 seconds: " << firstMinuteOverlap << " px\n"
              << "Deepest overlap across all displayed ticks: " << worstOverlap
              << " px at frame " << worstFrame << '\n'
              << "Deepest overlap at finish: " << currentOverlap << " px\n"
              << "Serial grid: " << gridTime.count() << " ms\n"
              << "Threaded halo (" << halo.workerCount() << " workers): "
              << haloTime.count() << " ms\n"
              << "Halo / grid time: " << haloTime.count() / gridTime.count() << "x\n";
    return 0;
}
