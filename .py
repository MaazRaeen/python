#private
class Example:
    def __init__(self,a,b):
        self.__a=a
        self.__b=b
    def add(self):
        return self.__a+self.__b
e=Example(5,6)
e.add()
print(e.__a)
print(e.__b)