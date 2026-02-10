import './style.css'

// Scroll reveal animation
const revealElements = document.querySelectorAll('.reveal')

const revealOnScroll = () => {
  const windowHeight = window.innerHeight
  revealElements.forEach(el => {
    const elementTop = el.getBoundingClientRect().top
    const elementVisible = 150
    if (elementTop < windowHeight - elementVisible) {
      el.classList.add('visible')
    }
  })
}

window.addEventListener('scroll', revealOnScroll)
revealOnScroll()

// Smooth scroll for anchor links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
  anchor.addEventListener('click', function (e) {
    e.preventDefault()
    const target = document.querySelector(this.getAttribute('href'))
    if (target) {
      target.scrollIntoView({
        behavior: 'smooth',
        block: 'start'
      })
    }
  })
})

// Navigation background on scroll
const nav = document.querySelector('.nav')
let lastScroll = 0

window.addEventListener('scroll', () => {
  const currentScroll = window.pageYOffset

  if (currentScroll > 100) {
    nav.style.background = 'rgba(10, 15, 20, 0.95)'
    nav.style.borderBottom = '1px solid rgba(42, 53, 68, 0.5)'
  } else {
    nav.style.background = 'linear-gradient(to bottom, rgb(10, 15, 20), transparent)'
    nav.style.borderBottom = 'none'
  }

  lastScroll = currentScroll
})

// Code card animation - cycle through active states
const codeStandards = document.querySelectorAll('.code-standard')
let activeIndex = 0

const cycleCodeCards = () => {
  codeStandards.forEach((card, index) => {
    card.classList.toggle('active', index === activeIndex)
  })
  activeIndex = (activeIndex + 1) % codeStandards.length
}

if (codeStandards.length > 0) {
  setInterval(cycleCodeCards, 3000)
}

// Video play functionality
const videoOverlay = document.querySelector('.video-overlay')
const video = document.querySelector('.demo-video video')

if (videoOverlay && video) {
  video.addEventListener('play', () => {
    videoOverlay.style.display = 'none'
  })

  video.addEventListener('pause', () => {
    if (video.currentTime > 0) {
      videoOverlay.style.display = 'none'
    }
  })
}

// Add hover effect to code cards
document.querySelectorAll('.code-card').forEach(card => {
  card.addEventListener('mouseenter', () => {
    card.style.transform = 'translateY(-2px)'
    card.style.boxShadow = '0 8px 30px rgba(0, 212, 170, 0.1)'
  })

  card.addEventListener('mouseleave', () => {
    card.style.transform = ''
    card.style.boxShadow = ''
  })
})

// Example rows hover effect
document.querySelectorAll('.example-row:not(.example-header)').forEach(row => {
  row.addEventListener('mouseenter', () => {
    row.style.background = 'rgba(0, 212, 170, 0.05)'
  })

  row.addEventListener('mouseleave', () => {
    row.style.background = ''
  })
})

console.log('EHR Code Mapper Landing Page Loaded')
