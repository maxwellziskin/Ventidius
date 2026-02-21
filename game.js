// ============================================================
// SIGMA DERBY - Core Game Logic
// ============================================================

const HORSE_COLORS = ['#e74c3c', '#3498db', '#2ecc71', '#f1c40f', '#9b59b6'];
const HORSE_NAMES = ['Crimson Bolt', 'Blue Thunder', 'Green Machine', 'Gold Rush', 'Purple Reign'];
const NUM_HORSES = 5;

// Track geometry: an oval path defined as a rounded rectangle
// The track path follows the midline between inner and outer rails
// Midline between outer rail (rect 40,40 720x320 r160) and inner rail (rect 120,100 560x200 r100)
const TRACK = {
    cx: 400,       // center x
    cy: 200,       // center y
    rx: 130,       // semicircle radius at curves
    ry: 130,
    straightLen: 380, // length of each horizontal straight
};

// Compute total track perimeter for parameterization
const TRACK_PERIMETER = 2 * TRACK.straightLen + 2 * Math.PI * TRACK.rx;

// Given a parameter t in [0, 1), return the {x, y} position on the oval track.
// t=0 is the top center (finish line), going clockwise.
function trackPosition(t, laneOffset) {
    laneOffset = laneOffset || 0;
    const dist = t * TRACK_PERIMETER;
    const halfStraight = TRACK.straightLen / 2;
    const curveLen = Math.PI * TRACK.rx;
    const cx = TRACK.cx;
    const cy = TRACK.cy;
    const rx = TRACK.rx + laneOffset;
    const ry = TRACK.ry + laneOffset;

    // Segment 1: top straight, going right from center (0 to halfStraight)
    if (dist < halfStraight) {
        return { x: cx + dist, y: cy - TRACK.ry - laneOffset };
    }
    // Segment 2: right curve (halfStraight to halfStraight + curveLen)
    const d1 = dist - halfStraight;
    if (d1 < curveLen) {
        const angle = -Math.PI / 2 + (d1 / curveLen) * Math.PI;
        return {
            x: cx + halfStraight + rx * Math.cos(angle),
            y: cy + ry * Math.sin(angle)
        };
    }
    // Segment 3: bottom straight, going left (halfStraight + curveLen to 2*halfStraight + curveLen)
    const d2 = d1 - curveLen;
    if (d2 < TRACK.straightLen) {
        return { x: cx + halfStraight - d2, y: cy + TRACK.ry + laneOffset };
    }
    // Segment 4: left curve
    const d3 = d2 - TRACK.straightLen;
    const angle = Math.PI / 2 + (d3 / curveLen) * Math.PI;
    return {
        x: cx - halfStraight + rx * Math.cos(angle),
        y: cy + ry * Math.sin(angle)
    };
}

// ============================================================
// ODDS GENERATION
// ============================================================

// The 10 quinella combos for 5 horses
function getQuinellaCombos() {
    const combos = [];
    for (let i = 0; i < NUM_HORSES; i++) {
        for (let j = i + 1; j < NUM_HORSES; j++) {
            combos.push([i, j]);
        }
    }
    return combos;
}

const QUINELLA_COMBOS = getQuinellaCombos();

// Possible odds values, mimicking the real machine's range
const ODDS_POOL = [2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, 50, 60, 80, 100, 150, 200];

// Generate odds for a race. The result is predetermined first,
// then odds are assigned so the winning combo has appropriately weighted odds.
function generateRaceOdds(winnerCombo) {
    // Assign odds to each combo. The winner should generally have lower odds
    // (favorites win more often) but sometimes longshots hit.
    const odds = {};

    // Decide what odds the winner gets (weighted toward lower odds)
    const winnerOddsOptions = [
        { odds: 2, weight: 25 },
        { odds: 3, weight: 20 },
        { odds: 4, weight: 15 },
        { odds: 5, weight: 12 },
        { odds: 6, weight: 8 },
        { odds: 8, weight: 6 },
        { odds: 10, weight: 5 },
        { odds: 15, weight: 3 },
        { odds: 20, weight: 2 },
        { odds: 25, weight: 1.5 },
        { odds: 30, weight: 1 },
        { odds: 40, weight: 0.5 },
        { odds: 50, weight: 0.3 },
        { odds: 60, weight: 0.2 },
        { odds: 80, weight: 0.15 },
        { odds: 100, weight: 0.1 },
        { odds: 150, weight: 0.05 },
        { odds: 200, weight: 0.02 },
    ];

    const winnerOddsVal = weightedRandom(winnerOddsOptions);
    const winKey = comboKey(winnerCombo);
    odds[winKey] = winnerOddsVal;

    // Fill in other combos with random odds, biased so they form a plausible board
    for (const combo of QUINELLA_COMBOS) {
        const key = comboKey(combo);
        if (key === winKey) continue;

        // Other combos get random odds from the full pool
        const idx = Math.floor(Math.random() * ODDS_POOL.length);
        odds[key] = ODDS_POOL[idx];
    }

    // Ensure there's a reasonable spread: at least one low and one high
    return odds;
}

function weightedRandom(options) {
    const totalWeight = options.reduce((sum, o) => sum + o.weight, 0);
    let r = Math.random() * totalWeight;
    for (const opt of options) {
        r -= opt.weight;
        if (r <= 0) return opt.odds;
    }
    return options[options.length - 1].odds;
}

function comboKey(combo) {
    return `${Math.min(combo[0], combo[1])}-${Math.max(combo[0], combo[1])}`;
}

// ============================================================
// RACE SIMULATION
// ============================================================

// Predetermine race results: returns an ordered array [1st, 2nd, 3rd, 4th, 5th]
function determineRaceResult() {
    const horses = [0, 1, 2, 3, 4];
    // Fisher-Yates shuffle
    for (let i = horses.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [horses[i], horses[j]] = [horses[j], horses[i]];
    }
    return horses;
}

// Generate movement curves for each horse so the predetermined result plays out.
// Returns an array of 5 arrays, each containing progress values at each tick.
function generateRaceAnimation(result, totalTicks) {
    const numLaps = 2;
    const totalDistance = numLaps; // in laps

    // Each horse needs a final position that matches the result order.
    // Horse at result[0] finishes first, result[1] second, etc.
    // We'll give them base speeds and add randomized "jockeying" noise.

    const finishGap = 0.03; // gap between finishing positions in laps
    const horses = [];

    for (let h = 0; h < NUM_HORSES; h++) {
        const finishPlace = result.indexOf(h);
        const targetDist = totalDistance - finishPlace * finishGap;
        horses.push({
            targetDist,
            finishPlace,
            progress: [] // will hold progress at each tick
        });
    }

    // Generate smooth movement with noise
    for (let h = 0; h < NUM_HORSES; h++) {
        const target = horses[h].targetDist;
        const baseSpeed = target / totalTicks;
        let pos = 0;

        // Create some random "energy" phases where horse speeds up or slows
        const numPhases = 5 + Math.floor(Math.random() * 4);
        const phases = [];
        for (let p = 0; p < numPhases; p++) {
            phases.push({
                start: Math.random(),
                duration: 0.05 + Math.random() * 0.15,
                intensity: (Math.random() - 0.5) * baseSpeed * 1.2
            });
        }

        for (let tick = 0; tick < totalTicks; tick++) {
            const t = tick / totalTicks;

            // Base speed with slight acceleration curve
            let speed = baseSpeed;

            // Apply phase modifiers
            for (const phase of phases) {
                if (t >= phase.start && t < phase.start + phase.duration) {
                    const phaseT = (t - phase.start) / phase.duration;
                    // Smooth bell curve within phase
                    const envelope = Math.sin(phaseT * Math.PI);
                    speed += phase.intensity * envelope;
                }
            }

            // Add small random jitter
            speed += (Math.random() - 0.5) * baseSpeed * 0.3;

            // Ensure horse doesn't go backwards
            speed = Math.max(baseSpeed * 0.2, speed);

            // In the final stretch, guide horse toward exact target
            const remaining = target - pos;
            const ticksLeft = totalTicks - tick;
            if (ticksLeft < totalTicks * 0.15) {
                const neededSpeed = remaining / ticksLeft;
                speed = speed * 0.3 + neededSpeed * 0.7;
            }

            pos += speed;
            horses[h].progress.push(pos);
        }

        // Normalize so last tick lands exactly at target
        const finalPos = horses[h].progress[totalTicks - 1];
        const scale = target / finalPos;
        for (let tick = 0; tick < totalTicks; tick++) {
            horses[h].progress[tick] *= scale;
        }
    }

    return horses.map(h => h.progress);
}

// ============================================================
// GAME STATE
// ============================================================

const state = {
    coins: 100,
    raceNumber: 1,
    phase: 'betting', // 'betting' | 'racing' | 'results'
    odds: {},
    bets: {},         // { comboKey: amount }
    selectedCombo: null,
    raceResult: null,
    animations: null,
    currentTick: 0,
    totalTicks: 300,
    animFrameId: null,
    horsePositions: [0, 0, 0, 0, 0], // current t values on track
};

// ============================================================
// RENDERING
// ============================================================

function createHorseMarkers() {
    const svg = document.getElementById('track');
    for (let i = 0; i < NUM_HORSES; i++) {
        const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        g.id = `horse-${i}`;
        g.classList.add('horse-marker');

        // Shadow
        const shadow = document.createElementNS('http://www.w3.org/2000/svg', 'ellipse');
        shadow.setAttribute('rx', '8');
        shadow.setAttribute('ry', '4');
        shadow.setAttribute('fill', 'rgba(0,0,0,0.3)');
        shadow.setAttribute('cy', '6');
        g.appendChild(shadow);

        // Body circle
        const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        circle.setAttribute('r', '10');
        circle.setAttribute('fill', HORSE_COLORS[i]);
        circle.setAttribute('stroke', '#fff');
        circle.setAttribute('stroke-width', '2');
        g.appendChild(circle);

        // Number
        const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        text.classList.add('horse-number');
        text.textContent = i + 1;
        text.setAttribute('fill', '#fff');
        text.setAttribute('dy', '1');
        g.appendChild(text);

        svg.appendChild(g);
    }
}

function updateHorsePositions() {
    for (let i = 0; i < NUM_HORSES; i++) {
        const t = state.horsePositions[i] % 1;
        const laneOffset = (i - 2) * 10; // spread horses across lanes
        const pos = trackPosition(t, laneOffset);
        const g = document.getElementById(`horse-${i}`);
        g.setAttribute('transform', `translate(${pos.x}, ${pos.y})`);
    }
}

function renderOddsGrid() {
    const grid = document.getElementById('odds-grid');
    grid.innerHTML = '';

    for (const combo of QUINELLA_COMBOS) {
        const key = comboKey(combo);
        const cell = document.createElement('div');
        cell.classList.add('odds-cell');
        cell.dataset.combo = key;

        if (state.phase !== 'betting') {
            cell.classList.add('disabled');
        }

        if (state.selectedCombo === key) {
            cell.classList.add('selected');
        }

        // Check if this is the winning combo
        if (state.phase === 'results' && state.raceResult) {
            const winKey = comboKey([state.raceResult[0], state.raceResult[1]]);
            if (key === winKey) {
                cell.classList.add('winner');
            }
        }

        const horseDots = document.createElement('div');
        horseDots.classList.add('odds-horses');
        for (const h of combo) {
            const dot = document.createElement('span');
            dot.classList.add('h-dot');
            dot.style.background = HORSE_COLORS[h];
            horseDots.appendChild(dot);
        }
        const label = document.createElement('span');
        label.style.fontSize = '11px';
        label.style.color = '#aaa';
        label.textContent = ` ${combo[0] + 1}-${combo[1] + 1}`;
        horseDots.appendChild(label);
        cell.appendChild(horseDots);

        const oddsVal = document.createElement('div');
        oddsVal.classList.add('odds-value');
        oddsVal.textContent = `${state.odds[key]}:1`;
        cell.appendChild(oddsVal);

        const betDisplay = document.createElement('div');
        betDisplay.classList.add('odds-bet');
        if (state.bets[key]) {
            betDisplay.textContent = `${state.bets[key]}Q bet`;
        }
        cell.appendChild(betDisplay);

        cell.addEventListener('click', () => selectCombo(key));
        grid.appendChild(cell);
    }
}

function renderCoins() {
    document.getElementById('coins').textContent = state.coins;
}

function renderStatus(text, className) {
    const el = document.getElementById('status-text');
    el.textContent = text;
    el.className = className || '';
}

function renderResults() {
    const banner = document.getElementById('results-banner');
    const content = document.getElementById('results-content');

    if (state.phase !== 'results') {
        banner.classList.add('hidden');
        return;
    }

    banner.classList.remove('hidden');

    const r = state.raceResult;
    const winCombo = comboKey([r[0], r[1]]);
    const winOdds = state.odds[winCombo];

    let html = `<div class="winner-line">`;
    html += `#${r[0] + 1} ${HORSE_NAMES[r[0]]} & #${r[1] + 1} ${HORSE_NAMES[r[1]]}`;
    html += `</div>`;
    html += `<div style="color:#aaa;font-size:13px;margin-bottom:8px;">Quinella ${r[0]+1}-${r[1]+1} paid ${winOdds}:1</div>`;

    // Check all bets for payouts
    let totalWin = 0;
    let totalBet = 0;
    for (const [key, amount] of Object.entries(state.bets)) {
        totalBet += amount;
        if (key === winCombo) {
            const payout = amount * winOdds;
            totalWin += payout;
        }
    }

    if (totalBet === 0) {
        html += `<div style="color:#888;">No bets placed</div>`;
    } else if (totalWin > 0) {
        html += `<div class="payout-line">WIN! +${totalWin} quarters!</div>`;
    } else {
        html += `<div class="loss-line">No winners this race (-${totalBet}Q)</div>`;
    }

    // Full results
    html += `<div style="color:#666;font-size:12px;margin-top:8px;">`;
    html += `Finish: `;
    for (let i = 0; i < NUM_HORSES; i++) {
        html += `${i + 1}st #${r[i] + 1}  `.replace('1st', i === 0 ? '1st' : i === 1 ? '2nd' : i === 2 ? '3rd' : `${i + 1}th`);
    }
    html += `</div>`;

    content.innerHTML = html;
}

function renderRaceNumber() {
    const el = document.getElementById('race-number-display');
    if (el) el.textContent = `RACE #${state.raceNumber}`;
}

function render() {
    renderOddsGrid();
    renderCoins();
    renderResults();
    renderRaceNumber();
    updateHorsePositions();

    // Update button states
    const raceBtn = document.getElementById('btn-race');
    if (state.phase !== 'betting') {
        raceBtn.classList.add('disabled');
    } else {
        raceBtn.classList.remove('disabled');
    }
}

// ============================================================
// INTERACTION
// ============================================================

function selectCombo(key) {
    if (state.phase !== 'betting') return;
    state.selectedCombo = (state.selectedCombo === key) ? null : key;
    renderOddsGrid();
}

function placeBet(amount) {
    if (state.phase !== 'betting') return;
    if (!state.selectedCombo) return;
    if (state.coins < amount) return;

    if (!state.bets[state.selectedCombo]) {
        state.bets[state.selectedCombo] = 0;
    }
    state.bets[state.selectedCombo] += amount;
    state.coins -= amount;
    render();
}

function clearBets() {
    if (state.phase !== 'betting') return;
    // Refund all bets
    for (const amount of Object.values(state.bets)) {
        state.coins += amount;
    }
    state.bets = {};
    state.selectedCombo = null;
    render();
}

// ============================================================
// RACE EXECUTION
// ============================================================

function startRace() {
    if (state.phase !== 'betting') return;

    state.phase = 'racing';
    state.selectedCombo = null;

    // Result was already predetermined when odds were generated

    // Generate animation curves
    state.animations = generateRaceAnimation(state.raceResult, state.totalTicks);
    state.currentTick = 0;

    // Reset horse positions
    state.horsePositions = [0, 0, 0, 0, 0];

    renderStatus('RACE IN PROGRESS', 'racing');
    render();

    // Start animation loop
    runRaceAnimation();
}

function runRaceAnimation() {
    if (state.currentTick >= state.totalTicks) {
        finishRace();
        return;
    }

    const tick = state.currentTick;

    // Update horse positions from animation data
    for (let i = 0; i < NUM_HORSES; i++) {
        state.horsePositions[i] = state.animations[i][tick];
    }

    updateHorsePositions();
    state.currentTick++;

    state.animFrameId = requestAnimationFrame(runRaceAnimation);
}

function finishRace() {
    state.phase = 'results';

    // Calculate payouts
    const winCombo = comboKey([state.raceResult[0], state.raceResult[1]]);
    let totalWin = 0;

    for (const [key, amount] of Object.entries(state.bets)) {
        if (key === winCombo) {
            const payout = amount * state.odds[winCombo];
            totalWin += payout;
        }
    }

    state.coins += totalWin;

    const r = state.raceResult;
    renderStatus(
        `FINISH: #${r[0]+1} ${HORSE_NAMES[r[0]]} & #${r[1]+1} ${HORSE_NAMES[r[1]]}`,
        'finished'
    );
    render();

    // After a delay, set up next race
    setTimeout(() => {
        setupNextRace();
    }, 5000);
}

function setupNextRace() {
    state.raceNumber++;
    state.phase = 'betting';
    state.bets = {};
    state.selectedCombo = null;

    // Predetermine the next race result and generate odds
    const nextResult = determineRaceResult();
    state.raceResult = nextResult;
    state.odds = generateRaceOdds(nextResult);

    // Place horses at starting positions (spread slightly)
    for (let i = 0; i < NUM_HORSES; i++) {
        state.horsePositions[i] = 0.97 + i * 0.005;
    }

    document.getElementById('results-banner').classList.add('hidden');
    renderStatus('PLACE YOUR BETS');
    render();
}

// ============================================================
// INITIALIZATION
// ============================================================

function init() {
    createHorseMarkers();

    // Set up first race (predetermine result and odds)
    state.raceResult = determineRaceResult();
    state.odds = generateRaceOdds(state.raceResult);

    // Place horses at starting positions
    for (let i = 0; i < NUM_HORSES; i++) {
        state.horsePositions[i] = 0.97 + i * 0.005;
    }

    // Wire up buttons
    document.getElementById('btn-bet-1').addEventListener('click', () => placeBet(1));
    document.getElementById('btn-bet-5').addEventListener('click', () => placeBet(5));
    document.getElementById('btn-clear').addEventListener('click', clearBets);
    document.getElementById('btn-race').addEventListener('click', startRace);

    render();
}

init();
