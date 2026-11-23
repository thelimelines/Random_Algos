#include "Simulation.hpp"

#include <algorithm>
#include <array>
#include <atomic>
#include <cmath>
#include <condition_variable>
#include <cstring>
#include <exception>
#include <functional>
#include <mutex>
#include <thread>
#include <utility>

namespace physics
{
namespace
{
constexpr float diameter = 2.f * ballRadius;
constexpr float searchDistance = diameter + 4.f;
constexpr float refreshDistance = 1.9f;
constexpr float penetrationSlop = 0.01f;
constexpr int solverSweeps = 16;
constexpr float farWall = windowSize - ballRadius;
constexpr float gravity = 720.f;
constexpr float contactSpeedLimit = 900.f;
constexpr int cellSize = 20;
constexpr int gridSize = (windowSize + cellSize - 1) / cellSize;
constexpr int tileSize = 9;
constexpr int tilesPerSide = (gridSize + tileSize - 1) / tileSize;
constexpr int tileCount = tilesPerSide * tilesPerSide;
constexpr std::size_t maxBalls = 3000;
constexpr std::size_t spawnInterval = 2 * substepsPerTick;
constexpr std::mt19937::result_type seed = 20261123;
static_assert(cellSize >= searchDistance, "Candidate pairs must fit within a one-cell halo");

using BallIndex = std::size_t;
using Contact = std::pair<BallIndex, BallIndex>;
using Contacts = std::vector<Contact>;

struct Grid
{
    std::array<std::vector<BallIndex>, gridSize * gridSize> cells;

    const std::vector<BallIndex>& at(int column, int row) const
    {
        return cells[row * gridSize + column];
    }

    void rebuild(const std::vector<Ball>& balls)
    {
        for (auto& cell : cells)
            cell.clear();

        for (BallIndex id = 0; id < balls.size(); ++id)
        {
            const int column = static_cast<int>(balls[id].x) / cellSize;
            const int row = static_cast<int>(balls[id].y) / cellSize;
            cells[row * gridSize + column].push_back(id);
        }
    }
};

void collectContact(const std::vector<Ball>& balls, BallIndex first, BallIndex second,
                    Contacts& contacts)
{
    const float dx = balls[second].x - balls[first].x;
    const float dy = balls[second].y - balls[first].y;
    if (dx * dx + dy * dy < searchDistance * searchDistance)
        contacts.emplace_back(std::min(first, second), std::max(first, second));
}

void collectGridContacts(const Grid& grid, const std::vector<Ball>& balls,
                         int left, int top, int right, int bottom, Contacts& contacts)
{
    // Only visit the forward half of the neighborhood, so each pair has one owner.
    constexpr int offsets[][2] = {{1, 0}, {-1, 1}, {0, 1}, {1, 1}};
    for (int row = top; row < bottom; ++row)
    {
        for (int column = left; column < right; ++column)
        {
            const auto& cell = grid.at(column, row);
            if (cell.empty())
                continue;

            for (std::size_t first = 0; first < cell.size(); ++first)
                for (std::size_t second = first + 1; second < cell.size(); ++second)
                    collectContact(balls, cell[first], cell[second], contacts);

            for (const auto& offset : offsets)
            {
                const int neighborColumn = column + offset[0];
                const int neighborRow = row + offset[1];
                if (neighborColumn < 0 || neighborColumn >= gridSize || neighborRow >= gridSize)
                    continue;

                // A neighboring cell can be outside the tile, in its read-only halo.
                for (BallIndex first : cell)
                    for (BallIndex second : grid.at(neighborColumn, neighborRow))
                        collectContact(balls, first, second, contacts);
            }
        }
    }
}

class HaloWorkers
{
public:
    HaloWorkers()
        : results_(std::clamp(std::thread::hardware_concurrency(), 2u, 8u))
    {
        threads_.reserve(results_.size());
        try
        {
            for (auto& result : results_)
                threads_.emplace_back(&HaloWorkers::work, this, std::ref(result));
        }
        catch (...)
        {
            stop();
            throw;
        }
    }

    ~HaloWorkers() { stop(); }

    unsigned count() const { return static_cast<unsigned>(threads_.size()); }

    void collect(const Grid& grid, const std::vector<Ball>& balls, Contacts& contacts)
    {
        Job job{grid, balls};
        {
            std::lock_guard<std::mutex> lock(mutex_);
            job_ = &job;
            remaining_ = threads_.size();
            ++generation_;
        }
        ready_.notify_all();

        {
            std::unique_lock<std::mutex> lock(mutex_);
            finished_.wait(lock, [this] { return remaining_ == 0; });
            job_ = nullptr;
        }

        for (const auto& result : results_)
        {
            if (result.error)
                std::rethrow_exception(result.error);
            contacts.insert(contacts.end(), result.contacts.begin(), result.contacts.end());
        }
    }

private:
    struct Job
    {
        const Grid& grid;
        const std::vector<Ball>& balls;
        std::atomic<int> nextTile{0};
    };

    struct Result
    {
        Contacts contacts;
        std::exception_ptr error;
    };

    void work(Result& result)
    {
        std::size_t seen = 0;
        std::unique_lock<std::mutex> lock(mutex_);
        for (;;)
        {
            ready_.wait(lock, [this, seen] { return stopping_ || generation_ != seen; });
            if (stopping_)
                return;

            seen = generation_;
            Job& job = *job_;
            lock.unlock();

            result.contacts.clear();
            result.error = nullptr;
            try
            {
                // Assign tiles dynamically because balls tend to pile up along the floor.
                for (int tile = job.nextTile.fetch_add(1, std::memory_order_relaxed);
                     tile < tileCount;
                     tile = job.nextTile.fetch_add(1, std::memory_order_relaxed))
                {
                    const int left = (tile % tilesPerSide) * tileSize;
                    const int top = (tile / tilesPerSide) * tileSize;
                    collectGridContacts(job.grid, job.balls, left, top,
                                        std::min(left + tileSize, gridSize),
                                        std::min(top + tileSize, gridSize), result.contacts);
                }
            }
            catch (...)
            {
                result.error = std::current_exception();
            }

            lock.lock();
            if (--remaining_ == 0)
                finished_.notify_one();
        }
    }

    void stop()
    {
        {
            std::lock_guard<std::mutex> lock(mutex_);
            stopping_ = true;
        }
        ready_.notify_all();
        for (auto& thread : threads_)
            thread.join();
    }

    std::vector<Result> results_;
    std::vector<std::thread> threads_;
    std::mutex mutex_;
    std::condition_variable ready_;
    std::condition_variable finished_;
    Job* job_ = nullptr;
    std::size_t remaining_ = 0;
    std::size_t generation_ = 0;
    bool stopping_ = false;
};

void predictPosition(Ball& ball)
{
    const float dx = ball.x - ball.previousX;
    const float dy = ball.y - ball.previousY + gravity * stepSeconds * stepSeconds;
    ball.previousX = ball.x;
    ball.previousY = ball.y;
    ball.x = std::clamp(ball.x + dx, ballRadius, farWall);
    ball.y = std::clamp(ball.y + dy, ballRadius, farWall);
}

float displacementSquared(const Ball& ball)
{
    const float dx = ball.x - ball.previousX;
    const float dy = ball.y - ball.previousY;
    return dx * dx + dy * dy;
}

void limitContactDisplacement(Ball& ball, float predictedDisplacementSquared)
{
    // Deep contacts at the emitter should separate promptly without launching
    // balls at extreme speeds. Preserve any speed already reached in free flight.
    constexpr float limit = contactSpeedLimit * stepSeconds;
    const float allowedSquared = std::max(limit * limit, predictedDisplacementSquared);
    const float actualSquared = displacementSquared(ball);
    if (actualSquared > allowedSquared)
    {
        const float scale = std::sqrt(allowedSquared / actualSquared);
        ball.previousX = ball.x - (ball.x - ball.previousX) * scale;
        ball.previousY = ball.y - (ball.y - ball.previousY) * scale;
    }
}

void separateAxis(float& first, float& second, float separation)
{
    const float half = separation * 0.5f;
    const float firstTarget = first - half;
    const float secondTarget = second + half;
    if (firstTarget >= ballRadius && firstTarget <= farWall
        && secondTarget >= ballRadius && secondTarget <= farWall)
    {
        first = firstTarget;
        second = secondTarget;
        return;
    }

    const float firstStart = first;
    const float secondStart = second;
    first = std::clamp(firstTarget, ballRadius, farWall);
    // Give any correction blocked by a wall to the ball that still has room.
    second = std::clamp(secondStart + separation + (first - firstStart), ballRadius, farWall);
    first = std::clamp(firstStart + (second - secondStart) - separation, ballRadius, farWall);
}

bool resolveContact(Ball& first, Ball& second)
{
    const float dx = second.x - first.x;
    const float dy = second.y - first.y;
    const float distanceSquared = dx * dx + dy * dy;
    // An earlier contact may already have separated this pair.
    constexpr float targetDistance = diameter - penetrationSlop;
    if (distanceSquared >= targetDistance * targetDistance)
        return false;

    const float distance = std::sqrt(distanceSquared);
    const float normalX = distance > 0.f ? dx / distance : 1.f;
    const float normalY = distance > 0.f ? dy / distance : 0.f;
    const float correction = targetDistance - distance;
    separateAxis(first.x, second.x, normalX * correction);
    separateAxis(first.y, second.y, normalY * correction);
    return true;
}

bool sameFloat(float first, float second)
{
    return std::memcmp(&first, &second, sizeof(float)) == 0;
}

bool sameBall(const Ball& first, const Ball& second)
{
    return sameFloat(first.x, second.x) && sameFloat(first.y, second.y)
        && sameFloat(first.previousX, second.previousX)
        && sameFloat(first.previousY, second.previousY);
}
}

struct Simulation::CollisionWorkspace
{
    Grid grid;
    Contacts contacts;
    std::vector<Ball> searchPositions;
    std::vector<float> predictedDisplacementsSquared;
    std::unique_ptr<HaloWorkers> workers;
};

Simulation::Simulation(CollisionMode mode, std::vector<Ball> initialBalls)
    : mode_(mode), balls_(std::move(initialBalls)), random_(seed),
      collision_(std::make_unique<CollisionWorkspace>())
{
    balls_.reserve(maxBalls);
    if (mode_ == CollisionMode::Halo)
        collision_->workers = std::make_unique<HaloWorkers>();
}

Simulation::~Simulation() = default;

void Simulation::reset()
{
    balls_.clear();
    collision_->contacts.clear();
    random_.seed(seed);
    step_ = 0;
}

void Simulation::findCandidates()
{
    collision_->searchPositions = balls_;
    auto& contacts = collision_->contacts;
    contacts.clear();
    if (mode_ == CollisionMode::Naive)
    {
        for (BallIndex first = 0; first < balls_.size(); ++first)
            for (BallIndex second = first + 1; second < balls_.size(); ++second)
                collectContact(balls_, first, second, contacts);
    }
    else
    {
        auto& grid = collision_->grid;
        grid.rebuild(balls_);
        if (mode_ == CollisionMode::Grid)
            collectGridContacts(grid, balls_, 0, 0, gridSize, gridSize, contacts);
        else
            collision_->workers->collect(grid, balls_, contacts);

        // The naive loop already emits this order. Only the solver writes ball state.
        std::sort(contacts.begin(), contacts.end());
    }
}

void Simulation::advance(bool spawnEnabled)
{
    if (spawnEnabled && step_ % spawnInterval == 0 && balls_.size() < maxBalls)
    {
        const float y = spawnY + static_cast<float>(random_() % 15) - 7.f;
        const float vx = 300.f + static_cast<float>(random_() % 321);
        const float vy = static_cast<float>(random_() % 81) - 40.f;
        balls_.push_back({spawnX, y, vx, vy});
    }
    ++step_;
    auto& predicted = collision_->predictedDisplacementsSquared;
    predicted.resize(balls_.size());
    for (std::size_t id = 0; id < balls_.size(); ++id)
    {
        predictPosition(balls_[id]);
        predicted[id] = displacementSquared(balls_[id]);
    }

    findCandidates();
    const auto& contacts = collision_->contacts;
    const auto& searchPositions = collision_->searchPositions;
    for (int sweep = 0; sweep < solverSweeps && !contacts.empty(); ++sweep)
    {
        bool changed = false;
        for (std::size_t offset = 0; offset < contacts.size(); ++offset)
        {
            // Sweeping in both directions helps corrections travel through a pile.
            const auto& [first, second] =
                contacts[sweep % 2 == 0 ? offset : contacts.size() - 1 - offset];
            changed |= resolveContact(balls_[first], balls_[second]);
        }
        if (!changed)
            break;

        bool refresh = false;
        for (std::size_t id = 0; id < balls_.size(); ++id)
        {
            const auto& ball = balls_[id];
            const float dx = ball.x - searchPositions[id].x;
            const float dy = ball.y - searchPositions[id].y;
            refresh |= dx * dx + dy * dy > refreshDistance * refreshDistance;
        }
        // Two balls can each move by half the search margin before we need new pairs.
        if (refresh && sweep + 1 < solverSweeps)
            findCandidates();
    }

    for (std::size_t id = 0; id < balls_.size(); ++id)
        limitContactDisplacement(balls_[id], predicted[id]);
}

unsigned Simulation::workerCount() const
{
    return collision_->workers ? collision_->workers->count() : 0;
}

bool Simulation::sameState(const Simulation& other) const
{
    return step_ == other.step_ && balls_.size() == other.balls_.size()
        && collision_->contacts == other.collision_->contacts
        && std::equal(balls_.begin(), balls_.end(), other.balls_.begin(), sameBall);
}
}
