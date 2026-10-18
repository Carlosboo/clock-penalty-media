import React from 'react';
import {
  AbsoluteFill,
  Composition,
  OffthreadVideo,
  registerRoot,
  spring,
  staticFile,
  useCurrentFrame,
} from 'remotion';
import data from '../public/timeline.json';
import { FPS, DURATION, ROWS, anchors, captionGroups } from './timeline.mjs';

const mint = '#73f8c9';
const gold = '#ffe399';
const bg = '#061d2c';
const triggers = anchors(data.words);
const groups = captionGroups(data.words);
const ease = { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' };
const pop = (frame, delay = 0) =>
  spring({
    frame: frame - delay,
    fps: FPS,
    config: { damping: 17, stiffness: 180, mass: 0.8 },
  });
const glass = {
  background: 'rgba(6,29,44,.87)',
  backdropFilter: 'blur(22px)',
  border: '1.5px solid rgba(168,235,221,.35)',
  borderRadius: 28,
  boxShadow: '0 20px 65px rgba(0,0,0,.25)',
};

function Icon({ kind, done = false }) {
  const paths = {
    database: (
      <>
        <ellipse cx="32" cy="14" rx="23" ry="9" />
        <path d="M9 14v36c0 12 46 12 46 0V14M9 32c0 12 46 12 46 0" />
      </>
    ),
    cloud: <path d="M14 49h34a12 12 0 0 0 0-24A19 19 0 0 0 12 22a14 14 0 0 0 2 27Z" />,
    live: (
      <>
        <rect x="4" y="12" width="17" height="40" rx="4" />
        <rect x="43" y="12" width="17" height="40" rx="4" />
        <path d="M25 25h14m-5-5 5 5-5 5M39 39H25m5-5-5 5 5 5" />
      </>
    ),
    shield: (
      <>
        <path d="m32 4 24 10-4 27-20 18-20-18-4-27Z" />
        <path d="m20 31 9 9 16-19" />
      </>
    ),
  };
  return (
    <svg
      width="58"
      height="58"
      viewBox="0 0 64 64"
      fill="none"
      stroke={done ? mint : gold}
      strokeWidth="3"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {paths[kind]}
    </svg>
  );
}

function Captions({ frame }) {
  const t = frame / FPS;
  const group = groups.find((item) => t >= item.start && t < item.end);
  if (!group) return null;
  return (
    <div
      style={{
        position: 'absolute',
        left: 140,
        top: 1290,
        width: 800,
        height: 110,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 13,
        fontSize: 56,
        fontWeight: 800,
        letterSpacing: -1.5,
        textShadow: '0 3px 10px #000, 0 0 4px #000',
      }}
    >
      {group.words.map((word, i) => {
        const active = t >= word.start && t < word.end;
        const appear = pop(frame, Math.round(word.start * FPS));
        return (
          <span
            key={i}
            style={{
              color: active ? bg : 'white',
              background: active ? mint : 'transparent',
              borderRadius: 12,
              padding: '5px 8px',
              opacity: t < word.start ? 0.6 : 1,
              textShadow: active ? 'none' : '0 3px 10px #000, 0 0 4px #000',
              transform: `translateY(${active ? (1 - appear) * 10 : 0}px)`,
            }}
          >
            {word.word}
          </span>
        );
      })}
    </div>
  );
}

function Checklist({ frame }) {
  const start = triggers[0] - 12;
  const enter = pop(frame, start);
  const completed = triggers.filter((value) => frame >= value).length;
  if (frame < start || frame >= 727) return null;
  return (
    <div
      style={{
        ...glass,
        position: 'absolute',
        left: 90,
        top: 900,
        width: 850,
        padding: '24px 30px',
        boxSizing: 'border-box',
        opacity: Math.min(1, enter),
        transformOrigin: '50% 0',
        transform: `translateY(${(1 - enter) * 70}px) perspective(1000px) rotateX(${(1 - enter) * -12}deg)`,
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: 23,
          letterSpacing: 2,
          color: '#e0eee9',
        }}
      >
        <span>EL STACK DE CLOCK PENALTY</span>
        <span style={{ color: mint }}>{completed}/4</span>
      </div>
      <div
        style={{
          height: 4,
          background: '#36505a',
          marginTop: 13,
          marginBottom: 12,
          borderRadius: 4,
        }}
      >
        <div style={{ width: `${completed * 25}%`, height: '100%', background: mint }} />
      </div>
      {ROWS.map((row, i) => {
        const active = frame >= triggers[i];
        const done = i < ROWS.length - 1 && frame >= triggers[i + 1];
        const reveal = pop(frame, triggers[i]);
        return (
          <div
            key={row.title}
            style={{
              height: 69,
              display: 'flex',
              gap: 18,
              alignItems: 'center',
              opacity: active ? 1 : 0.34,
            }}
          >
            <div
              style={{
                width: 26,
                height: 26,
                borderRadius: '50%',
                border: `2px solid ${done ? mint : '#78909b'}`,
                color: mint,
                fontSize: 23,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              {done ? '✓' : ''}
            </div>
            {active ? (
              <>
                <div style={{ transform: `scale(${0.8 + reveal * 0.2})` }}>
                  <Icon kind={row.kind} done={done} />
                </div>
                <div style={{ transform: `translateX(${(1 - reveal) * 22}px)` }}>
                  <div style={{ fontSize: 30, fontWeight: 750, color: done ? '#e4efe9' : mint }}>
                    {row.title}
                  </div>
                  <div style={{ fontSize: 20, color: '#bed0d5' }}>{row.detail}</div>
                </div>
              </>
            ) : (
              <div
                style={{ width: 310 - i * 22, height: 13, borderRadius: 7, background: '#78909b' }}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

export function Creator({ captions = true }) {
  const frame = useCurrentFrame();
  const live = frame >= 436 && frame < 593;
  const end = frame >= 727;
  const punch =
    !live && !end
      ? 0.035 *
        Math.exp(
          -Math.max(
            0,
            frame -
              (frame < 63 ? 0 : frame < 247 ? 63 : frame < 321 ? 247 : frame < 436 ? 321 : 593),
          ) / 18,
        )
      : 0;
  return (
    <AbsoluteFill
      style={{ backgroundColor: bg, color: 'white', fontFamily: 'DejaVu Sans, sans-serif' }}
    >
      <AbsoluteFill
        style={{ transform: `translateY(${!live && !end ? -190 : 0}px) scale(${1 + punch})` }}
      >
        <OffthreadVideo
          src={staticFile('base.mp4')}
          muted
          style={{ width: '100%', height: '100%' }}
        />
      </AbsoluteFill>
      {!end && (
        <AbsoluteFill
          style={{
            background:
              'linear-gradient(180deg,rgba(6,29,44,.42),transparent 28%,transparent 42%,rgba(6,29,44,.38) 66%,rgba(6,29,44,.9))',
          }}
        />
      )}
      {!end && (
        <div
          style={{
            position: 'absolute',
            left: 90,
            top: 155,
            fontSize: 24,
            color: mint,
            letterSpacing: 2,
          }}
        >
          @clock.penalty <span style={{ color: '#e0ebe6', marginLeft: 24 }}>DEVLOG / 001</span>
        </div>
      )}
      {frame < 63 && (
        <div
          style={{
            position: 'absolute',
            top: 930,
            left: 90,
            width: 850,
            transform: `translateY(${(1 - pop(frame)) * 60}px)`,
            opacity: Math.min(1, pop(frame)),
          }}
        >
          <div style={{ fontSize: 23, letterSpacing: 5, color: mint }}>UN EXPERIMENTO REAL</div>
          <div style={{ fontSize: 88, lineHeight: 1.06, fontWeight: 850 }}>
            Un vídeo.
            <br />
            Un poco de <span style={{ color: gold }}>IA.</span>
          </div>
        </div>
      )}
      {frame >= 63 && frame < 247 && (
        <div style={{ position: 'absolute', top: 1010, left: 90, width: 850 }}>
          <div style={{ fontSize: 24, color: mint, letterSpacing: 3 }}>
            ASÍ LO ESTOY CONSTRUYENDO
          </div>
          <div
            style={{
              fontSize: 71,
              fontWeight: 800,
              transform: `translateY(${(1 - pop(frame, 63)) * 30}px)`,
            }}
          >
            Dentro de
            <br />
            <span style={{ color: gold }}>Clock Penalty.</span>
          </div>
        </div>
      )}
      <Checklist frame={frame} />
      {live && (
        <div
          style={{
            position: 'absolute',
            left: 90,
            top: 250,
            fontSize: 23,
            color: gold,
            letterSpacing: 2,
          }}
        >
          GAMEPLAY · VERSIÓN DE DESARROLLO
        </div>
      )}
      {frame >= 635 && frame < 727 && (
        <div style={{ position: 'absolute', left: 90, top: 1418, fontSize: 22, color: gold }}>
          Antitrampas: validación de jugadas en servidor
        </div>
      )}
      {captions && <Captions frame={frame} />}
      {end && (
        <AbsoluteFill
          style={{
            justifyContent: 'center',
            padding: '0 100px',
            boxSizing: 'border-box',
            transform: `translateY(${(1 - pop(frame, 727)) * 25}px)`,
          }}
        >
          <div style={{ fontSize: 25, letterSpacing: 5, color: mint }}>
            UN JUEGO QUE ESTOY CREANDO
          </div>
          <div style={{ fontSize: 92, fontWeight: 850, lineHeight: 1.04, marginTop: 25 }}>
            CLOCK
            <br />
            <span style={{ color: mint }}>PENALTY</span>
          </div>
          <div style={{ fontSize: 36, marginTop: 40 }}>Pruébalo. Dime qué mejorarías.</div>
          <div style={{ ...glass, marginTop: 65, padding: '28px 22px', color: gold, fontSize: 39 }}>
            clockpenalty.com
          </div>
          <div style={{ fontSize: 28, marginTop: 40, color: mint }}>@clock.penalty</div>
        </AbsoluteFill>
      )}
      <div
        style={{
          position: 'absolute',
          left: 90,
          top: 1450,
          width: 850,
          height: 4,
          background: 'rgba(255,255,255,.18)',
        }}
      >
        <div
          style={{ height: '100%', width: `${(frame / (DURATION - 1)) * 100}%`, background: mint }}
        />
      </div>
    </AbsoluteFill>
  );
}

registerRoot(() => (
  <>
    <Composition
      id="Creator"
      component={Creator}
      durationInFrames={DURATION}
      fps={FPS}
      width={1080}
      height={1920}
      defaultProps={{ captions: true }}
    />
    <Composition
      id="CreatorClean"
      component={Creator}
      durationInFrames={DURATION}
      fps={FPS}
      width={1080}
      height={1920}
      defaultProps={{ captions: false }}
    />
  </>
));
