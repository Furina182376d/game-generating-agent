/* Parameterized bullet-hell shooter template (Phaser 3).
 * {{GAME_CONFIG}} is replaced with a JSON GameConfig at generation time.
 * Full flow: BootScene -> MenuScene -> PlayScene -> GameOverScene -> restart.
 * Responsive: scales to the viewport, supports keyboard + touch.
 */
const CONFIG = {{GAME_CONFIG}};

const WIDTH = 480;
const HEIGHT = 720;

// ---- fallback textures ----------------------------------------------------
// If an asset failed to resolve, we draw a simple colored shape so the game
// always runs (requirement 3: no blocking errors).
function makeFallback(scene, key, color, w, h) {
  const g = scene.make.graphics({ x: 0, y: 0, add: false });
  g.fillStyle(color, 1);
  g.fillRect(0, 0, w, h);
  g.generateTexture(key, w, h);
  g.destroy();
}

// ---- Boot: load assets ----------------------------------------------------
class BootScene extends Phaser.Scene {
  constructor() { super("Boot"); }
  preload() {
    if (CONFIG.player.sprite) this.load.image("player", CONFIG.player.sprite);
    if (CONFIG.background) this.load.image("bg", CONFIG.background);
    CONFIG.enemies.forEach((e, i) => {
      if (e.sprite) this.load.image("enemy" + i, e.sprite);
    });
  }
  create() {
    if (!this.textures.exists("player")) makeFallback(this, "player", 0x44ddff, 40, 40);
    if (!this.textures.exists("bg")) makeFallback(this, "bg", 0x0b0e1a, WIDTH, HEIGHT);
    makeFallback(this, "bullet", 0xffee55, 6, 14);
    makeFallback(this, "ebullet", 0xff5566, 6, 12);
    CONFIG.enemies.forEach((e, i) => {
      if (!this.textures.exists("enemy" + i)) {
        makeFallback(this, "enemy" + i, 0xff8844, 36, 36);
      }
    });
    this.scene.start("Menu");
  }
}

// ---- Menu: start flow -----------------------------------------------------
class MenuScene extends Phaser.Scene {
  constructor() { super("Menu"); }
  create() {
    this.add.image(WIDTH / 2, HEIGHT / 2, "bg").setDisplaySize(WIDTH, HEIGHT);
    this.add.text(WIDTH / 2, HEIGHT / 2 - 80, CONFIG.title, {
      fontSize: "32px", color: "#ffffff", fontStyle: "bold",
    }).setOrigin(0.5);
    this.add.text(WIDTH / 2, HEIGHT / 2, "Tap / Press SPACE to start", {
      fontSize: "18px", color: "#aad4ff",
    }).setOrigin(0.5);
    this.add.text(WIDTH / 2, HEIGHT / 2 + 40, "Move: arrows / drag   Fire: auto", {
      fontSize: "13px", color: "#7788aa",
    }).setOrigin(0.5);

    const start = () => this.scene.start("Play");
    this.input.keyboard.once("keydown-SPACE", start);
    this.input.once("pointerdown", start);
  }
}

// ---- Game over: end + restart flow ---------------------------------------
class GameOverScene extends Phaser.Scene {
  constructor() { super("GameOver"); }
  init(data) { this.won = data.won; this.score = data.score; }
  create() {
    this.add.image(WIDTH / 2, HEIGHT / 2, "bg").setDisplaySize(WIDTH, HEIGHT);
    this.add.text(WIDTH / 2, HEIGHT / 2 - 60, this.won ? "YOU WIN" : "GAME OVER", {
      fontSize: "36px", color: this.won ? "#66ff99" : "#ff6677", fontStyle: "bold",
    }).setOrigin(0.5);
    this.add.text(WIDTH / 2, HEIGHT / 2, "Score: " + this.score, {
      fontSize: "22px", color: "#ffffff",
    }).setOrigin(0.5);
    this.add.text(WIDTH / 2, HEIGHT / 2 + 50, "Tap / SPACE to play again", {
      fontSize: "16px", color: "#aad4ff",
    }).setOrigin(0.5);

    const restart = () => this.scene.start("Play");
    this.input.keyboard.once("keydown-SPACE", restart);
    this.input.once("pointerdown", restart);
  }
}

// ---- Play: core gameplay --------------------------------------------------
class PlayScene extends Phaser.Scene {
  constructor() { super("Play"); }

  create() {
    this.score = 0;
    this.lives = CONFIG.player.lives;
    this.lastFire = 0;
    this.lastSpawn = 0;
    this.elapsed = 0;

    // scrolling background
    this.bg = this.add.tileSprite(WIDTH / 2, HEIGHT / 2, WIDTH, HEIGHT, "bg");

    // player
    this.player = this.physics.add.sprite(WIDTH / 2, HEIGHT - 80, "player");
    this.player.setCollideWorldBounds(true).setDisplaySize(44, 44);

    // groups
    this.bullets = this.physics.add.group();
    this.enemies = this.physics.add.group();
    this.ebullets = this.physics.add.group();

    // input
    this.cursors = this.input.keyboard.createCursorKeys();
    this.pointerTarget = null;
    this.input.on("pointermove", (p) => {
      if (p.isDown) this.pointerTarget = { x: p.x * (WIDTH / this.scale.width) };
    });
    this.input.on("pointerdown", (p) => {
      this.pointerTarget = { x: p.x * (WIDTH / this.scale.width) };
    });
    this.input.on("pointerup", () => { this.pointerTarget = null; });

    // collisions
    this.physics.add.overlap(this.bullets, this.enemies, this.hitEnemy, null, this);
    this.physics.add.overlap(this.player, this.enemies, this.hitPlayer, null, this);
    this.physics.add.overlap(this.player, this.ebullets, this.hitPlayer, null, this);

    // HUD
    this.hud = this.add.text(10, 10, "", { fontSize: "16px", color: "#ffffff" });
    this.updateHud();
  }

  updateHud() {
    this.hud.setText(
      `Score ${this.score}/${CONFIG.target_score}   Lives ${this.lives}`
    );
  }

  update(time, delta) {
    this.elapsed += delta;
    this.bg.tilePositionY -= 0.5;

    // --- movement ---
    const speed = CONFIG.player.speed;
    this.player.setVelocity(0);
    if (this.pointerTarget) {
      const dx = this.pointerTarget.x - this.player.x;
      if (Math.abs(dx) > 4) this.player.setVelocityX(Math.sign(dx) * speed);
    } else {
      if (this.cursors.left.isDown) this.player.setVelocityX(-speed);
      else if (this.cursors.right.isDown) this.player.setVelocityX(speed);
      if (this.cursors.up.isDown) this.player.setVelocityY(-speed);
      else if (this.cursors.down.isDown) this.player.setVelocityY(speed);
    }

    // --- auto fire ---
    if (time - this.lastFire > CONFIG.player.fire_rate * 1000) {
      this.lastFire = time;
      const b = this.bullets.create(this.player.x, this.player.y - 24, "bullet");
      b.setVelocityY(-500);
    }

    // --- spawn enemies (difficulty scales spawn rate over time) ---
    const ramp = CONFIG.difficulty === "hard" ? 0.6
      : CONFIG.difficulty === "easy" ? 1.4 : 1.0;
    const interval = Math.max(350, (1100 - this.elapsed / 40)) * ramp;
    if (time - this.lastSpawn > interval) {
      this.lastSpawn = time;
      this.spawnEnemy();
    }

    // --- cull + enemy behavior ---
    this.enemies.children.iterate((e) => {
      if (!e) return;
      if (e.y > HEIGHT + 40) e.destroy();
      else if (e.getData("pattern") === "zigzag") {
        e.setVelocityX(Math.sin(e.y / 40) * 160);
      }
    });
    this.bullets.children.iterate((b) => { if (b && b.y < -20) b.destroy(); });
    this.ebullets.children.iterate((b) => { if (b && b.y > HEIGHT + 20) b.destroy(); });

    if (this.score >= CONFIG.target_score) this.endGame(true);
  }

  spawnEnemy() {
    const idx = Phaser.Math.Between(0, CONFIG.enemies.length - 1);
    const spec = CONFIG.enemies[idx];
    const x = Phaser.Math.Between(30, WIDTH - 30);
    const e = this.enemies.create(x, -30, "enemy" + idx);
    e.setDisplaySize(36, 36);
    e.setData("hp", spec.hp);
    e.setData("pattern", spec.type);
    e.setData("score", 10 * spec.hp);
    e.setVelocityY(spec.speed);
    if (spec.type === "homing") {
      const dx = this.player.x - x;
      e.setVelocityX(Phaser.Math.Clamp(dx, -100, 100));
    }
  }

  hitEnemy(bullet, enemy) {
    bullet.destroy();
    const hp = enemy.getData("hp") - 1;
    if (hp <= 0) {
      this.score += enemy.getData("score");
      enemy.destroy();
      this.updateHud();
    } else {
      enemy.setData("hp", hp);
      enemy.setTint(0xffaaaa);
    }
  }

  hitPlayer(player, hazard) {
    hazard.destroy();
    this.lives -= 1;
    this.updateHud();
    this.cameras.main.shake(150, 0.01);
    if (this.lives <= 0) this.endGame(false);
  }

  endGame(won) {
    this.scene.start("GameOver", { won, score: this.score });
  }
}

// ---- boot the game --------------------------------------------------------
new Phaser.Game({
  type: Phaser.AUTO,
  parent: "game",
  width: WIDTH,
  height: HEIGHT,
  backgroundColor: "#0b0e1a",
  physics: { default: "arcade", arcade: { debug: false } },
  scale: {
    mode: Phaser.Scale.FIT,
    autoCenter: Phaser.Scale.CENTER_BOTH,
  },
  scene: [BootScene, MenuScene, PlayScene, GameOverScene],
});

