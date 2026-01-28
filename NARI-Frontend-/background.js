// Three.js Background Scene
const canvas = document.getElementById('bg-canvas');
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });

renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

// Particles
const particlesGeometry = new THREE.BufferGeometry();
const particlesCount = 2000;
const posArray = new Float32Array(particlesCount * 3);

for (let i = 0; i < particlesCount * 3; i++) {
    posArray[i] = (Math.random() - 0.5) * 12;
}

particlesGeometry.setAttribute('position', new THREE.BufferAttribute(posArray, 3));

const particlesMaterial = new THREE.PointsMaterial({
    size: 0.012,
    color: 0x8b5cf6,
    transparent: true,
    opacity: 0.7,
    blending: THREE.AdditiveBlending
});

const particlesMesh = new THREE.Points(particlesGeometry, particlesMaterial);
scene.add(particlesMesh);

// Floating geometric shapes
const shapes = [];

// Icosahedron
const geo1 = new THREE.IcosahedronGeometry(0.5, 0);
const mat1 = new THREE.MeshBasicMaterial({
    color: 0x6366f1,
    wireframe: true,
    transparent: true,
    opacity: 0.25
});
const icosahedron = new THREE.Mesh(geo1, mat1);
icosahedron.position.set(-3, 1.5, -2);
scene.add(icosahedron);
shapes.push({ mesh: icosahedron, rotSpeed: { x: 0.004, y: 0.007 } });

// Octahedron
const geo2 = new THREE.OctahedronGeometry(0.4, 0);
const mat2 = new THREE.MeshBasicMaterial({
    color: 0xa855f7,
    wireframe: true,
    transparent: true,
    opacity: 0.25
});
const octahedron = new THREE.Mesh(geo2, mat2);
octahedron.position.set(3.5, -1.5, -3);
scene.add(octahedron);
shapes.push({ mesh: octahedron, rotSpeed: { x: 0.006, y: 0.004 } });

// Torus
const geo3 = new THREE.TorusGeometry(0.35, 0.12, 8, 16);
const mat3 = new THREE.MeshBasicMaterial({
    color: 0x60a5fa,
    wireframe: true,
    transparent: true,
    opacity: 0.2
});
const torus = new THREE.Mesh(geo3, mat3);
torus.position.set(2.5, 2.5, -4);
scene.add(torus);
shapes.push({ mesh: torus, rotSpeed: { x: 0.005, y: 0.008 } });

// Dodecahedron
const geo4 = new THREE.DodecahedronGeometry(0.3, 0);
const mat4 = new THREE.MeshBasicMaterial({
    color: 0xc084fc,
    wireframe: true,
    transparent: true,
    opacity: 0.22
});
const dodecahedron = new THREE.Mesh(geo4, mat4);
dodecahedron.position.set(-2.5, -2, -3.5);
scene.add(dodecahedron);
shapes.push({ mesh: dodecahedron, rotSpeed: { x: 0.007, y: 0.005 } });

camera.position.z = 3;

// Mouse interaction
let mouseX = 0;
let mouseY = 0;
let targetX = 0;
let targetY = 0;

document.addEventListener('mousemove', (e) => {
    mouseX = (e.clientX / window.innerWidth) * 2 - 1;
    mouseY = -(e.clientY / window.innerHeight) * 2 + 1;
});

// Animation
function animate() {
    requestAnimationFrame(animate);

    // Smooth mouse parallax
    targetX += (mouseX - targetX) * 0.05;
    targetY += (mouseY - targetY) * 0.05;

    // Rotate particles
    particlesMesh.rotation.y += 0.0003;
    particlesMesh.rotation.x += 0.0001;

    // Mouse parallax on particles
    particlesMesh.rotation.y += targetX * 0.0008;
    particlesMesh.rotation.x += targetY * 0.0005;

    // Rotate shapes
    shapes.forEach(shape => {
        shape.mesh.rotation.x += shape.rotSpeed.x;
        shape.mesh.rotation.y += shape.rotSpeed.y;
    });

    renderer.render(scene, camera);
}

animate();

// Resize handler
window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
});
