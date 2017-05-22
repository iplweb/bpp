# -*- coding: utf-8 -*-
# -*- mode: ruby -*-
# vi: set ft=ruby :

# Wymagane pluginy:
#
#  * vagrant-hostmanager
#  * vagrant-cachier


Vagrant.configure(2) do |config|

  if Vagrant.has_plugin?("vagrant-hostmanager")
      config.hostmanager.enabled = true
      config.hostmanager.manage_host = true
      config.hostmanager.ignore_private_ip = false
      config.hostmanager.include_offline = true
   end

  config.vm.define "master", primary: true do |master|
      master.vm.box = "ubuntu/xenial64"
      master.vm.box_check_update = false

      master.vm.hostname = 'bpp-master'

      if Vagrant.has_plugin?("vagrant-hostmanager")
          master.hostmanager.aliases = %w(bpp-master.localnet)
      end

      if Vagrant.has_plugin?("vagrant-timezone")
      	 master.timezone.value = :host
      end

      master.vm.provider "virtualbox" do |vb|
          vb.customize ["modifyvm", :id, "--cpus", "4"]
          vb.customize ["modifyvm", :id, "--memory", "2048"]
      end

      master.vm.network "private_network", ip: "192.168.111.100"

      if Vagrant.has_plugin?("vagrant-cachier")
        master.cache.scope = :box
        master.cache.enable :apt
        master.cache.enable :npm
	master.cache.enable :generic, {
	  "wget" => { cache_dir: "/var/cache/wget" },
	  "pip" => { cache_dir: "/home/ubuntu/.cache/pip" }
	}
      end

      master.vm.provision "shell", inline: "sudo apt install python-minimal -y"
      master.vm.provision "ansible" do |ansible|
        ansible.playbook = "ansible/provision.yml"
      end

  end

  config.vm.define "staging" do |staging|
      staging.vm.box = "ubuntu/xenial64"
      staging.vm.box_check_update = false
 
      staging.vm.provider "virtualbox" do |vb|
          vb.customize ["modifyvm", :id, "--cpus", "4"]
      end
 
      staging.vm.hostname = 'bpp-staging'
      if Vagrant.has_plugin?("vagrant-hostmanager")
          staging.hostmanager.aliases = %w(bpp-staging.localnet)
      end

      if Vagrant.has_plugin?("vagrant-timezone")
      	 staging.timezone.value = :host
      end

      staging.vm.network "private_network", ip: "192.168.111.101"

      staging.vm.provision "shell", inline: "sudo apt install python-minimal -y"
      staging.vm.provision "ansible" do |ansible|
        ansible.playbook = "ansible/provision.yml"
      end

      if Vagrant.has_plugin?("vagrant-reload")
            staging.vm.provision :reload
      end

      if Vagrant.has_plugin?("vagrant-cachier")
        staging.cache.scope = :box
        staging.cache.enable :apt
        staging.cache.enable :npm
      end

  end

  config.vm.define "db" do |db|
      db.vm.box = "ubuntu/xenial64"
      db.vm.box_check_update = false

      db.vm.hostname = 'bpp-db'
      if Vagrant.has_plugin?("vagrant-hostmanager")
          db.hostmanager.aliases = %w(bpp-db.localnet)
      end
      db.vm.network "private_network", ip: "192.168.111.102"

      db.vm.provision "shell", inline: "sudo apt install python-minimal -y"
      db.vm.provision "ansible" do |ansible|
        ansible.playbook = "ansible/provision.yml"
      end

      if Vagrant.has_plugin?("vagrant-timezone")
      	 db.timezone.value = :host
      end

      db.vm.provider "virtualbox" do |vb|
          vb.customize ["modifyvm", :id, "--cpus", "4"]
      end

      if Vagrant.has_plugin?("vagrant-reload")
            db.vm.provision :reload
      end
 
      if Vagrant.has_plugin?("vagrant-cachier")
        db.cache.scope = :box
        db.cache.enable :apt
        db.cache.enable :npm
      end

  end

  config.vm.define "selenium" do |selenium|
      selenium.vm.box = "ubuntu/xenial64"
      selenium.vm.box_check_update = false

      selenium.vm.hostname = 'bpp-selenium'
      selenium.vm.network "private_network", ip: "192.168.111.150"

      selenium.ssh.username = "ubuntu"
      if Vagrant.has_plugin?("vagrant-hostmanager")
          selenium.hostmanager.aliases = %w(bpp-selenium.localnet)
      end

      # Nie wiem czy to potrzebne:
      # selenium.vm.provision "shell", inline: "echo 192.168.111.1 MacOSX.localnet >> /etc/hosts"

      if Vagrant.has_plugin?("vagrant-cachier")
        selenium.cache.scope = :box
        selenium.cache.enable :apt
        selenium.cache.enable :npm
	selenium.cache.enable :generic, {
	  "wget" => { cache_dir: "/var/cache/wget" },
	  "pip" => { cache_dir: "/home/ubuntu/.cache/pip" },
	}
      end


      if Vagrant.has_plugin?("vagrant-timezone")
      	 selenium.timezone.value = :host
      end

      selenium.vm.provider "virtualbox" do |vb|
          vb.customize ["modifyvm", :id, "--cpus", "4"]
          vb.customize ["modifyvm", :id, "--memory", "2048"]
      end

      selenium.vm.provision "shell", inline: "sudo apt install python-minimal -y"
      selenium.vm.provision "ansible" do |ansible|
        # ansible.verbose = "v"
        ansible.playbook = "ansible/provision.yml"
      end

      if Vagrant.has_plugin?("vagrant-reload")
            selenium.vm.provision :reload
      end

  end

end
