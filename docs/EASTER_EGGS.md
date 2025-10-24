# TeckoChecker Easter Eggs

Welcome to the hidden features of TeckoChecker Web UI!

## Terminal Commands

The terminal input at the bottom of the Web UI is now functional. Type any of these commands and press **ENTER**:

### Available Commands

| Command | Description |
|---------|-------------|
| `help` | Show all available commands |
| `about` | Display information about TeckoChecker |
| `credits` | Show credits and acknowledgments (featuring Tomáš Trnka) |
| `snake` | Launch the Snake game |
| `hack` | Run a fake hacking sequence animation |
| `matrix` | Enter the Matrix (falling characters effect) |
| `refresh` | Refresh the current tab |
| `clear` | Clear the terminal input |

## Snake Game

Type `snake` in the terminal and press ENTER to launch a classic Snake game!

### Features
- **Terminal-style graphics** with green-on-black theme
- **Grid-based gameplay** (20x20 grid)
- **Smooth animations** with glowing effects
- **Progressive difficulty** - game speeds up as you collect food
- **Score tracking** - earn 10 points per food item

### Controls
- **Arrow Keys** - Move the snake (up, down, left, right)
- **ESC** - Exit game and return to dashboard
- **SPACE** - Restart game after game over

### Game Rules
- Collect red food items to grow and score points
- Avoid hitting walls
- Avoid running into yourself
- The snake grows longer with each food item
- Game speeds up gradually as you score more points

## Hacking Sequence

Type `hack` to watch a humorous fake hacking animation:
- Simulated connection to mainframe
- Bypassing firewalls
- Database decryption
- Just kidding message at the end!

**Press ESC or click outside** to close.

## Matrix Effect

Type `matrix` to experience the iconic Matrix falling characters:
- Full-screen cascading green characters
- Terminal aesthetics
- Authentic Matrix rain animation

**Press ESC or click outside** to exit the Matrix.

## Easter Egg Design

All easter eggs follow the terminal/hacker aesthetic:
- **Color scheme**: Green (#00ff41) on black background
- **Font**: Monospace terminal font
- **Effects**: Glowing text, shadows, and animations
- **Theme**: Retro hacker/cyberpunk vibe
- **Non-intrusive**: Easy to exit with ESC key

## Credits

**Inspired by**: Tomáš Trnka (tomas.trnka@live.com)
**Spiritual Father**: The visionary behind TeckoChecker

**Built with love and caffeine** by the TeckoChecker team.

---

## Implementation Details

### Files Modified
- `/app/web/static/js/app.js` - Added command handling and easter egg functions
- `/app/web/static/js/snake.js` - Complete Snake game implementation (150 lines)
- `/app/web/static/css/terminal.css` - Styling for game and effects
- `/app/web/static/index.html` - Added snake.js script reference

### Technical Highlights
- **Canvas-based rendering** for Snake game and Matrix effect
- **Event-driven architecture** for keyboard controls
- **Modal overlays** for immersive game experience
- **Animations** using CSS and JavaScript
- **Clean architecture** with separate Snake class
- **Memory management** - proper cleanup of intervals and event listeners

---

**Have fun exploring!** Type `help` in the terminal to get started.
