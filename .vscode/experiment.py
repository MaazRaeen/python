# import turtle
# t= turtle.turtle()
# s = turtle.Screen()
# colors = ['orange', 'red', 'magenta',
# 'blue', 'magenta', 'yellow', 'green',
# 'yellow', 'green', 'cyan', 'purplel' ]

# s.bgcolor('black')
# t.pensize(2)
# t.speed (0)

# for x in range (360 ):
#     # t.pencolor(colors[x x len(colors)])
#     t.pencolor(colors[x % len(colors)])

#     t.width(x//100+1)
#     t.forward (x)
#     t. right (B8)

# turtle.hideturtle
import turtle

t = turtle.Turtle()
s = turtle.Screen()
colors = ['orange', 'red', 'magenta',
          'blue', 'magenta', 'yellow', 'green',
          'yellow', 'green', 'cyan', 'purple']

s.bgcolor('black')
t.pensize(2)
t.speed(0)

for x in range(360):
    t.pencolor(colors[x % len(colors)])
    t.width(x // 100 + 1)
    t.forward(x)
    t.right(58)  # replace 58 with any angle you like for cool effects

t.hideturtle()
turtle.done()
