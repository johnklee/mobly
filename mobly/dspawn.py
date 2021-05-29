import os
import re
import inspect
import subprocess
import shlex
import time
import threading
from functools import partial
from mobly.logb import get_logger
from pexpect import ExceptionPexpect, TIMEOUT, EOF, spawn


class Error(Exception):
  """Base error type for adb proxy module."""


class DspawnTimeoutError(Error):
  """Raised when an action did not complete within expected time.

  Attributes:
    cmd: list of strings, the adb command that timed out
    timeout: float, the number of seconds passed before timing out.
    serial: string, the serial of the device the command is executed on.
      This is an empty string if the adb command is not specific to a
      device.
  """

  def __init__(self, msg, timeout, serial=''):
    super().__init__()
    self.msg = msg
    self.timeout = timeout
    self.serial = serial

  def __str__(self):
    return f'Timed out because of: {self.msg} (timeout={self.timeout},serial={self.serial})'


class StdoutReader(threading.Thread):
  def  __init__(self, stdout, max_queue_size=5000, encoding='utf8'):
    super(StdoutReader, self).__init__(name=self.__class__.__name__)
    self.logger = get_logger(self.__class__.__name__)
    self.stdout = stdout
    self.output = []
    self.encoding = encoding
    self.max_queue_size = max_queue_size
    self.ri = 0
    self.lock = threading.Lock() 

  def run(self): 
    for bline in iter(self.stdout.readline, b''):
      self.lock.acquire()
      line = bline.decode(self.encoding).strip()
      self.output.append(line)
      if len(self.output) > self.max_queue_size:
        del self.output[0]
        self.ri = self.ri - 1 if self.ri > 0 else self.ri

      self.lock.release()

  def readline(self, wait_time=1, wait_limit=1):
    line = None
    wait_count = 0
    self.lock.acquire()
    while True:
      if self.ri < len(self.output):
        line = self.output[self.ri]
        self.ri += 1
        break
      else:
        wait_count += 1
        if wait_count > wait_limit:
          break
        self.lock.release()
        time.sleep(wait_time)
        self.lock.acquire()

    self.lock.release()
    return line 


class Dspawn:
  def __init__(self, serial, shell=True, env=None):
    self.serial = serial
    command = f"adb -s {self.serial} shell"
    self.logger = get_logger(self.__class__.__name__)
    self.logger.debug(f"command={command}")
    args = shlex.split(command)
    self.logger.debug(f"args={args}")
    self.proc = subprocess.Popen(
      args,
      stdin=subprocess.PIPE,
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE,      
      # shell=shell,
      env={"PS1":"\\u:\\h "},
      preexec_fn=os.setsid
    )
    self.stdout_reader = StdoutReader(self.proc.stdout)
    self.stdout_reader.start()

    # used to match the command-line prompt
    self.UNIQUE_PROMPT_HEAD = "[PEXPECT]"
    self.UNIQUE_PROMPT = r"\[PEXPECT\][\$\#] "
    self.PROMPT = self.UNIQUE_PROMPT

    # used to set shell command-line prompt to UNIQUE_PROMPT.
    self.PROMPT_SET_SH = r"PS1='[PEXPECT]\$ '"
    self.PROMPT_SET_CSH = r"set prompt='[PEXPECT]\$ '"
    self.ENCODE = 'utf8'
    # self.set_unique_prompt()
        
  def set_unique_prompt(self):
    '''This sets the remote prompt to something more unique than ``#`` or ``$``.
    This makes it easier for the :meth:`prompt` method to match the shell prompt
    unambiguously. This method is called automatically by the :meth:`login`
    method, but you may want to call it manually if you somehow reset the
    shell prompt. For example, if you 'su' to a different user then you
    will need to manually reset the prompt. This sends shell commands to
    the remote host to set the prompt, so this assumes the remote host is
    ready to receive commands.

    Alternatively, you may use your own prompt pattern. In this case you
    should call :meth:`login` with ``auto_prompt_reset=False``; then set the
        :attr:`PROMPT` attribute to a regular expression. After that, the
        :meth:`prompt` method will try to match your prompt pattern.
    '''
    self.sendline("unset PROMPT_COMMAND")
    self.sendline(self.PROMPT_SET_SH) # sh-style
    i = self.expect([TIMEOUT, self.PROMPT], timeout=10)
    if i == 0: # csh-style
      self.sendline(self.PROMPT_SET_CSH)
      i = self.expect([TIMEOUT, self.PROMPT], timeout=10)
      if i == 0:
        return False
    return True

  def read(self):
    '''Read all
    '''
    output = []
    for line in iter(self.stdout_reader.readline, None):    
      self.logger.debug(line)
      output.append(line)

    return output

  def r(self, wait_time=1, wait_limit=1):
    '''Read line from stdout
    '''
    return self.readline(wait_time=wait_time, wait_limit=wait_limit)

  def readline(self, wait_time=1, wait_limit=1):
    '''Read line from stdout
    '''
    return self.stdout_reader.readline(wait_time=wait_time, wait_limit=wait_limit)

  def e(self, msg, is_regx=True, wait_time=1, wait_limit=1):
    return self.expect(msg, is_regx=is_regx, wait_time=wait_time, wait_limit=wait_limit)

  def expect(self, msg, is_regx=True, wait_time=1, wait_limit=1):
    '''Expect message from stdout
    '''
    cmp_rst = False
    self.logger.debug("read line1...")
    line = self.stdout_reader.readline(wait_time=wait_time, wait_limit=wait_limit)
    while line is not None:
      self.logger.debug(f"\tline={line}")
      if is_regx:
        cmp_rst = re.search(msg, line) is not None
      else:
        cmp_rst = line == msg

      if cmp_rst:
        return True

      self.logger.debug("read line2...")
      line = self.stdout_reader.readline(wait_time=wait_time, wait_limit=wait_limit)

    raise DspawnTimeoutError(
      f'Failed to search message={msg}',
      timeout=wait_time*wait_limit,
      serial=self.serial
    )

  def sendline(self, command):
    '''Send command into stdin
    '''
    self.proc.stdin.write(f"{command}\n".encode(self.ENCODE))
    self.proc.stdin.flush()

  def s(self, command):
    return self.sendline(command)

  def stop(self):
    if self.proc:
      self.s('exit')
      self.proc.terminate()

