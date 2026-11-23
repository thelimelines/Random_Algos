#include "FrameTiming.hpp"
#include "Simulation.hpp"

#include <SFML/Graphics.hpp>

#include <algorithm>
#include <array>
#include <cmath>
#include <exception>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string_view>
#include <vector>

int runBenchmark();

namespace
{
constexpr auto mode = physics::CollisionMode::PHYSICS_MODE;
constexpr char windowTitle[] = PHYSICS_TITLE " (Verlet)";
constexpr int circleSides = 16;

class BallDrawing
{
public:
    BallDrawing()
    {
        constexpr float fullTurn = 6.28318530718f;
        for (int side = 0; side < circleSides; ++side)
        {
            const float angle = fullTurn * side / circleSides;
            rim_[side] = physics::ballRadius * sf::Vector2f{std::cos(angle), std::sin(angle)};
        }
        rim_.back() = rim_.front();
    }

    void draw(sf::RenderTarget& target, const std::vector<physics::Ball>& balls)
    {
        static constexpr std::array colors{
            sf::Color{101, 201, 231}, sf::Color{255, 187, 108},
            sf::Color{117, 224, 177}, sf::Color{178, 163, 251}
        };
        vertices_.resize(balls.size() * circleSides * 3);
        auto vertex = vertices_.begin();
        for (std::size_t id = 0; id < balls.size(); ++id)
        {
            const sf::Vector2f center{balls[id].x, balls[id].y};
            const sf::Color color = colors[id % colors.size()];
            for (int side = 0; side < circleSides; ++side)
            {
                *vertex++ = {center, color, {}};
                *vertex++ = {center + rim_[side], color, {}};
                *vertex++ = {center + rim_[side + 1], color, {}};
            }
        }
        if (!vertices_.empty())
            target.draw(vertices_.data(), vertices_.size(), sf::PrimitiveType::Triangles);
    }

private:
    std::array<sf::Vector2f, circleSides + 1> rim_{};
    std::vector<sf::Vertex> vertices_;
};

void runWindow()
{
    sf::RenderWindow window(sf::VideoMode({physics::windowSize, physics::windowSize}),
                            windowTitle, sf::Style::Titlebar | sf::Style::Close);
    window.setFramerateLimit(physics::ticksPerSecond);
    window.setKeyRepeatEnabled(false);

    physics::Simulation simulation(mode);
    BallDrawing drawing;
    FrameTiming timing;
    sf::Clock clock;
    float elapsed = 0.f;
    float frameSeconds = 0.f;

    while (window.isOpen())
    {
        elapsed += std::min(frameSeconds, 0.1f);
        while (const auto event = window.pollEvent())
        {
            if (event->is<sf::Event::Closed>())
                window.close();
            if (const auto* key = event->getIf<sf::Event::KeyPressed>())
            {
                if (key->code == sf::Keyboard::Key::Escape)
                    window.close();
                if (key->code == sf::Keyboard::Key::R)
                {
                    simulation.reset();
                    elapsed = 0.f;
                }
            }
        }
        if (!window.isOpen())
            break;

        while (elapsed >= physics::tickSeconds)
        {
            for (int substep = 0; substep < physics::substepsPerTick; ++substep)
                simulation.advance(!timing.spawningPaused());
            elapsed -= physics::tickSeconds;
        }

        window.clear(sf::Color(16, 22, 34));
        drawing.draw(window, simulation.balls());
        window.display();

        frameSeconds = clock.restart().asSeconds();
        if (timing.recordFrame(frameSeconds))
        {
            std::ostringstream title;
            title << windowTitle << " | " << std::fixed << std::setprecision(1)
                  << timing.frameMilliseconds() << " ms | " << timing.fps() << " FPS";
            if (timing.spawningPaused())
                title << " | Spawning paused";
            window.setTitle(title.str());
        }
    }
}
}

int main(int argc, char* argv[])
{
    try
    {
        if (argc == 2 && std::string_view(argv[1]) == "--benchmark")
            return runBenchmark();
        if (argc != 1)
        {
            std::cerr << "Usage: " << argv[0] << " [--benchmark]\n";
            return 2;
        }
        runWindow();
    }
    catch (const std::exception& error)
    {
        std::cerr << error.what() << '\n';
        return 1;
    }
    return 0;
}
