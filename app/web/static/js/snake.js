/**
 * Snake Game - Terminal Edition
 * Classic Snake game with terminal aesthetics
 */

class SnakeGame {
    constructor() {
        this.gridSize = 20;
        this.tileSize = 20;
        this.snake = [{ x: 10, y: 10 }];
        this.food = this.generateFood();
        this.direction = { x: 1, y: 0 };
        this.nextDirection = { x: 1, y: 0 };
        this.score = 0;
        this.gameLoop = null;
        this.speed = 150; // ms per frame
        this.gameOver = false;
    }

    start() {
        // Create game modal
        const modal = document.createElement('div');
        modal.id = 'snake-game-modal';
        modal.className = 'modal active';
        modal.innerHTML = `
            <div class="modal-content game-container">
                <h2 class="game-title">SNAKE GAME</h2>
                <p class="game-instructions">
                    Arrow keys to move | ESC to exit
                </p>
                <canvas id="snake-canvas"></canvas>
                <div id="snake-score" class="game-score">Score: 0</div>
                <div id="game-over-message" class="game-over hidden">
                    GAME OVER<br>
                    Press SPACE to restart
                </div>
            </div>
        `;
        document.body.appendChild(modal);

        // Setup canvas
        this.canvas = document.getElementById('snake-canvas');
        this.ctx = this.canvas.getContext('2d');
        this.canvas.width = this.gridSize * this.tileSize;
        this.canvas.height = this.gridSize * this.tileSize;

        // Setup controls
        this.setupControls();

        // Start game loop
        this.run();

        // Handle modal close
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.close();
            }
        });
    }

    setupControls() {
        this.keyHandler = (e) => {
            switch(e.key) {
                case 'ArrowUp':
                    if (this.direction.y === 0) {
                        this.nextDirection = { x: 0, y: -1 };
                    }
                    e.preventDefault();
                    break;
                case 'ArrowDown':
                    if (this.direction.y === 0) {
                        this.nextDirection = { x: 0, y: 1 };
                    }
                    e.preventDefault();
                    break;
                case 'ArrowLeft':
                    if (this.direction.x === 0) {
                        this.nextDirection = { x: -1, y: 0 };
                    }
                    e.preventDefault();
                    break;
                case 'ArrowRight':
                    if (this.direction.x === 0) {
                        this.nextDirection = { x: 1, y: 0 };
                    }
                    e.preventDefault();
                    break;
                case 'Escape':
                    this.close();
                    e.preventDefault();
                    break;
                case ' ':
                    if (this.gameOver) {
                        this.restart();
                        e.preventDefault();
                    }
                    break;
            }
        };

        document.addEventListener('keydown', this.keyHandler);
    }

    generateFood() {
        let food;
        do {
            food = {
                x: Math.floor(Math.random() * this.gridSize),
                y: Math.floor(Math.random() * this.gridSize)
            };
        } while (this.snake.some(segment => segment.x === food.x && segment.y === food.y));
        return food;
    }

    update() {
        if (this.gameOver) return;

        // Update direction
        this.direction = this.nextDirection;

        // Calculate new head position
        const head = {
            x: this.snake[0].x + this.direction.x,
            y: this.snake[0].y + this.direction.y
        };

        // Check wall collision
        if (head.x < 0 || head.x >= this.gridSize || head.y < 0 || head.y >= this.gridSize) {
            this.endGame();
            return;
        }

        // Check self collision
        if (this.snake.some(segment => segment.x === head.x && segment.y === head.y)) {
            this.endGame();
            return;
        }

        // Add new head
        this.snake.unshift(head);

        // Check food collision
        if (head.x === this.food.x && head.y === this.food.y) {
            this.score += 10;
            this.food = this.generateFood();
            this.updateScore();
            // Speed up slightly
            if (this.speed > 50) {
                this.speed -= 2;
                this.restartLoop();
            }
        } else {
            // Remove tail
            this.snake.pop();
        }
    }

    draw() {
        // Clear canvas
        this.ctx.fillStyle = '#0a0a0a';
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

        // Draw grid
        this.ctx.strokeStyle = 'rgba(0, 255, 0, 0.1)';
        this.ctx.lineWidth = 1;
        for (let i = 0; i <= this.gridSize; i++) {
            // Vertical lines
            this.ctx.beginPath();
            this.ctx.moveTo(i * this.tileSize, 0);
            this.ctx.lineTo(i * this.tileSize, this.canvas.height);
            this.ctx.stroke();
            // Horizontal lines
            this.ctx.beginPath();
            this.ctx.moveTo(0, i * this.tileSize);
            this.ctx.lineTo(this.canvas.width, i * this.tileSize);
            this.ctx.stroke();
        }

        // Draw snake
        this.snake.forEach((segment, index) => {
            this.ctx.fillStyle = index === 0 ? '#00ff41' : '#00cc00';
            this.ctx.fillRect(
                segment.x * this.tileSize + 1,
                segment.y * this.tileSize + 1,
                this.tileSize - 2,
                this.tileSize - 2
            );

            // Add glow effect to head
            if (index === 0) {
                this.ctx.shadowColor = '#00ff41';
                this.ctx.shadowBlur = 10;
                this.ctx.fillStyle = '#00ff41';
                this.ctx.fillRect(
                    segment.x * this.tileSize + 1,
                    segment.y * this.tileSize + 1,
                    this.tileSize - 2,
                    this.tileSize - 2
                );
                this.ctx.shadowBlur = 0;
            }
        });

        // Draw food
        this.ctx.fillStyle = '#ff0040';
        this.ctx.shadowColor = '#ff0040';
        this.ctx.shadowBlur = 15;
        this.ctx.beginPath();
        this.ctx.arc(
            this.food.x * this.tileSize + this.tileSize / 2,
            this.food.y * this.tileSize + this.tileSize / 2,
            this.tileSize / 3,
            0,
            Math.PI * 2
        );
        this.ctx.fill();
        this.ctx.shadowBlur = 0;
    }

    run() {
        this.gameLoop = setInterval(() => {
            this.update();
            this.draw();
        }, this.speed);
    }

    restartLoop() {
        clearInterval(this.gameLoop);
        this.run();
    }

    updateScore() {
        const scoreEl = document.getElementById('snake-score');
        if (scoreEl) {
            scoreEl.textContent = `Score: ${this.score}`;
        }
    }

    endGame() {
        this.gameOver = true;
        clearInterval(this.gameLoop);

        const gameOverEl = document.getElementById('game-over-message');
        if (gameOverEl) {
            gameOverEl.classList.remove('hidden');
        }
    }

    restart() {
        // Reset game state
        this.snake = [{ x: 10, y: 10 }];
        this.food = this.generateFood();
        this.direction = { x: 1, y: 0 };
        this.nextDirection = { x: 1, y: 0 };
        this.score = 0;
        this.speed = 150;
        this.gameOver = false;

        // Update UI
        this.updateScore();
        const gameOverEl = document.getElementById('game-over-message');
        if (gameOverEl) {
            gameOverEl.classList.add('hidden');
        }

        // Restart loop
        this.run();
    }

    close() {
        // Clean up
        clearInterval(this.gameLoop);
        document.removeEventListener('keydown', this.keyHandler);

        // Remove modal
        const modal = document.getElementById('snake-game-modal');
        if (modal) {
            modal.remove();
        }
    }
}
