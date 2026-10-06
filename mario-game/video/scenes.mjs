// Each scene: setup() runs in the page after a fresh level; steps hold/tap keys for N game frames (60 fps).
// setup and js functions are serialised and run inside the game page, so they use its globals.
// {skip:true} steps run without recording; the first one lets Mario land before the clip starts.

const settle = {skip: true, frames: 30};

export const scenes = [
  {
    name: "banana", title: "Banana boomerang", key: "X",
    setup() {
      const g = (tx, vx = -0.5) => ents.push({kind:"enemy",type:"goomba",x:tx*T,y:12*T,w:16,h:16,vx,vy:0,state:"walk",t:0,onGround:false});
      mario.x = 3*T; g(8); g(9.2); g(10.4);
    },
    steps: [ settle, {frames: 16}, {tap: ["banana"], frames: 2}, {frames: 104} ],
  },
  {
    name: "dynamite", title: "Dynamite", key: "C",
    setup() {
      const g = (tx, vx = -0.5) => ents.push({kind:"enemy",type:"goomba",x:tx*T,y:12*T,w:16,h:16,vx,vy:0,state:"walk",t:0,onGround:false});
      mario.x = 3*T; g(10); g(11);
    },
    steps: [ settle, {frames: 16}, {tap: ["dyn"], frames: 2}, {frames: 110} ],
  },
  {
    name: "wings", title: "Wings", key: "F",
    setup() { mario.x = 5*T; giveWings(); },
    steps: [ settle, {hold: {right: true}, frames: 16}, {hold: {right: true, fly: true}, frames: 40},
             {hold: {right: true}, frames: 40}, {hold: {right: true, fly: true}, frames: 20}, {hold: {right: true}, frames: 64} ],
  },
  {
    name: "umbrella", title: "Bombers & umbrella", key: "U",
    setup() {
      const g = (tx, vx = -0.5) => ents.push({kind:"enemy",type:"goomba",x:tx*T,y:12*T,w:16,h:16,vx,vy:0,state:"walk",t:0,onGround:false});
      mario.x = 12*T; window.__camShift = 70;
      ents.push({kind:"enemy",type:"plane",x:mario.x-130,y:3*T,w:30,h:13,vx:PLANE_SPD,vy:0,dir:1,alt:3*T,ph:0,
                 cool:0,state:"fly",t:0,onGround:false});
      // the swatted bomb flies off to his left, into this one walking towards him
      g(12 - 180/T, 0.5);
    },
    steps: [ settle, {frames: 10}, {hold: {umbrella: true}, frames: 130}, {frames: 30} ],
  },
  {
    name: "laser", title: "Laser", key: "L",
    setup() {
      const g = (tx, vx = -0.5) => ents.push({kind:"enemy",type:"goomba",x:tx*T,y:12*T,w:16,h:16,vx,vy:0,state:"walk",t:0,onGround:false});
      mario.x = 3*T; g(9); g(10.5); g(12); g(13.5);
    },
    steps: [ settle, {frames: 16}, {tap: ["laser"], frames: 2}, {frames: 84} ],
  },
];
